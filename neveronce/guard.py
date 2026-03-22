"""NeverOnce Guard — Pre-flight correction checks for AI agent actions.

Decorators and utilities that intercept function calls, check NeverOnce
for applicable corrections, and warn/block/review before proceeding.

Zero external dependencies. Pure Python stdlib.
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from .memory import Memory

logger = logging.getLogger("neveronce.guard")

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CorrectionWarning(Exception):
    """Raised in BLOCK mode when corrections match a planned action.

    Attributes:
        corrections: List of matching correction dicts from NeverOnce.
        action: The planned action string that was checked.
    """

    def __init__(self, action: str, corrections: list[dict]):
        self.action = action
        self.corrections = corrections
        msgs = [c["content"] for c in corrections]
        super().__init__(
            f"Blocked by {len(corrections)} correction(s) for '{action}': "
            + "; ".join(msgs)
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_MODES = ("warn", "block", "review")


def _build_action_string(func: Callable, args: tuple, kwargs: dict) -> str:
    """Build a human-readable planned-action string from a function call."""
    import inspect

    parts = [func.__name__.replace("_", " ")]

    # Add docstring first line if available
    if func.__doc__:
        first_line = func.__doc__.strip().split("\n")[0].strip()
        if first_line:
            parts.append(first_line)

    # Map positional args to parameter names
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())
    named: dict[str, Any] = {}
    for i, val in enumerate(args):
        if i < len(param_names):
            named[param_names[i]] = val
    named.update(kwargs)

    if named:
        arg_strs = [f"{k}={v!r}" for k, v in named.items()]
        parts.append("with " + ", ".join(arg_strs))

    return " ".join(parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Core check function
# ---------------------------------------------------------------------------

def guard_tool_call(
    mem: Memory,
    tool_name: str,
    args_dict: dict | None = None,
    *,
    mode: str = "warn",
    reviewer: Callable | None = None,
) -> list[dict] | None:
    """Check corrections before a tool call without using a decorator.

    Args:
        mem: A NeverOnce Memory instance.
        tool_name: Name of the tool/function about to run.
        args_dict: Arguments being passed to the tool.
        mode: One of "warn", "block", "review".
        reviewer: Required callback when mode is "review".

    Returns:
        List of matching corrections, or None if no matches found.

    Raises:
        CorrectionWarning: In BLOCK mode when corrections match.
        ValueError: If mode is invalid or review mode lacks a reviewer.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if mode == "review" and reviewer is None:
        raise ValueError("review mode requires a reviewer callback")

    action_parts = [tool_name.replace("_", " ")]
    if args_dict:
        arg_strs = [f"{k}={v!r}" for k, v in args_dict.items()]
        action_parts.append("with " + ", ".join(arg_strs))
    action = " ".join(action_parts)

    corrections = mem.check(action)
    if not corrections:
        return None

    if mode == "warn":
        for c in corrections:
            logger.warning("NeverOnce correction: %s", c["content"])
        return corrections

    if mode == "block":
        raise CorrectionWarning(action, corrections)

    # mode == "review"
    return corrections if reviewer(action, corrections) else None


# ---------------------------------------------------------------------------
# @guard decorator
# ---------------------------------------------------------------------------

def guard(
    mem: Memory,
    *,
    mode: str = "warn",
    reviewer: Callable | None = None,
):
    """Decorator that adds pre-flight correction checks to a function.

    Args:
        mem: A NeverOnce Memory instance.
        mode: "warn" (log and proceed), "block" (raise CorrectionWarning),
              or "review" (call reviewer callback to decide).
        reviewer: A callable(action_str, corrections) -> bool that returns
                  True to proceed or False to block. Required for review mode.

    Example::

        @guard(mem, mode="warn")
        def send_email(to: str, subject: str):
            ...
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if mode == "review" and reviewer is None:
        raise ValueError("review mode requires a reviewer callback")

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            action = _build_action_string(func, args, kwargs)
            corrections = mem.check(action)

            outcome = "no_match"
            matched = []

            if corrections:
                matched = corrections
                if mode == "warn":
                    for c in corrections:
                        logger.warning("NeverOnce correction: %s", c["content"])
                    outcome = "warned"
                elif mode == "block":
                    outcome = "blocked"
                    _action_log_record(mem, func.__name__, args, kwargs, matched, outcome)
                    raise CorrectionWarning(action, corrections)
                elif mode == "review":
                    proceed = reviewer(action, corrections)
                    if not proceed:
                        outcome = "blocked_by_reviewer"
                        _action_log_record(mem, func.__name__, args, kwargs, matched, outcome)
                        raise CorrectionWarning(action, corrections)
                    outcome = "approved_by_reviewer"

            _action_log_record(mem, func.__name__, args, kwargs, matched, outcome)
            return func(*args, **kwargs)

        wrapper._neveronce_guarded = True
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# ActionLog
# ---------------------------------------------------------------------------

# Module-level log storage keyed by Memory instance id
_action_logs: dict[int, list[dict]] = {}


def _action_log_record(
    mem: Memory,
    func_name: str,
    args: tuple,
    kwargs: dict,
    corrections: list[dict],
    outcome: str,
) -> None:
    """Record an action to the in-memory action log."""
    key = id(mem)
    if key not in _action_logs:
        _action_logs[key] = []
    _action_logs[key].append({
        "action": func_name,
        "args": {f"arg{i}": v for i, v in enumerate(args)},
        "kwargs": kwargs,
        "corrections_matched": [
            {"id": c.get("id"), "content": c["content"]} for c in corrections
        ],
        "outcome": outcome,
        "timestamp": _now_iso(),
    })


class ActionLog:
    """Audit log for all guarded actions against a Memory instance.

    Automatically populated when ``@guard`` or ``GuardedAgent`` is used.

    Example::

        log = ActionLog(mem)
        entries = log.recent(limit=10)
    """

    def __init__(self, mem: Memory):
        self._mem = mem

    def recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent log entries, newest first."""
        key = id(self._mem)
        entries = _action_logs.get(key, [])
        return list(reversed(entries[-limit:]))

    def all(self) -> list[dict]:
        """Return all log entries, oldest first."""
        key = id(self._mem)
        return list(_action_logs.get(key, []))

    def clear(self) -> None:
        """Clear the action log."""
        key = id(self._mem)
        _action_logs.pop(key, None)

    def __len__(self) -> int:
        key = id(self._mem)
        return len(_action_logs.get(key, []))


# ---------------------------------------------------------------------------
# GuardedAgent
# ---------------------------------------------------------------------------

class GuardedAgent:
    """A lightweight agent wrapper that guards all registered tool calls.

    Args:
        memory: A NeverOnce Memory instance.
        mode: Default guard mode for all tools ("warn", "block", "review").
        reviewer: Default reviewer callback for review mode.

    Example::

        agent = GuardedAgent(memory=mem, mode="warn")

        @agent.tool
        def search_web(query: str) -> str:
            return do_search(query)

        result = agent.run("search_web", query="python best practices")
    """

    def __init__(
        self,
        memory: Memory,
        *,
        mode: str = "warn",
        reviewer: Callable | None = None,
    ):
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
        if mode == "review" and reviewer is None:
            raise ValueError("review mode requires a reviewer callback")
        self.memory = memory
        self.mode = mode
        self.reviewer = reviewer
        self._tools: dict[str, Callable] = {}

    def tool(self, func: Callable) -> Callable:
        """Register a function as a guarded tool.

        Can be used as a decorator::

            @agent.tool
            def my_tool(x: int) -> str:
                ...
        """
        guarded = guard(self.memory, mode=self.mode, reviewer=self.reviewer)(func)
        self._tools[func.__name__] = guarded
        return guarded

    def run(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool by name with pre-flight checks.

        Raises:
            KeyError: If the tool name is not registered.
        """
        if tool_name not in self._tools:
            available = ", ".join(sorted(self._tools)) or "(none)"
            raise KeyError(
                f"Unknown tool {tool_name!r}. Registered: {available}"
            )
        return self._tools[tool_name](**kwargs)

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return sorted(self._tools)
