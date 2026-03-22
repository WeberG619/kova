"""Ready-made integration patterns for popular AI agent frameworks.

All integrations are zero-dependency — framework imports are conditional.
Every function works with plain strings and dicts even if the framework
isn't installed. The core pattern: build a "planned action" string from
whatever the framework gives you, then call mem.check().

Usage without any framework installed:

    from neveronce import Memory
    from neveronce.integrations import generic_agent_guard

    mem = Memory("my_app")
    corrections = generic_agent_guard(mem, "send_email", {"to": "ceo@company.com"})
"""

from __future__ import annotations

from typing import Any

try:
    from .memory import Memory
except ImportError:
    Memory = None  # type: ignore[assignment,misc]


def _build_action_string(name: str, params: dict[str, Any] | None = None,
                         description: str = "") -> str:
    """Build a searchable action string from a tool name, its params, and description."""
    parts = [name]
    if description:
        parts.append(description)
    if params:
        for key, val in params.items():
            parts.append(f"{key}={val}")
    return " ".join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# Universal fallback — every other guard delegates to this
# ---------------------------------------------------------------------------

def generic_agent_guard(mem: Any, action_name: str,
                        action_params: dict[str, Any] | None = None,
                        description: str = "") -> list[dict] | None:
    """Check corrections before any agent action.

    Args:
        mem: A neveronce.Memory instance.
        action_name: Name of the action / tool / function.
        action_params: Key-value arguments for the action.
        description: Optional human-readable description of what the action does.

    Returns:
        List of matching correction dicts, or None if no corrections apply.

    Example::

        from neveronce import Memory
        from neveronce.integrations import generic_agent_guard

        mem = Memory("my_app")
        corrections = generic_agent_guard(mem, "deploy", {"env": "production"})
        if corrections:
            print("Blocked by corrections:", corrections)
    """
    planned = _build_action_string(action_name, action_params, description)
    matches = mem.check(planned)
    return matches if matches else None


# ---------------------------------------------------------------------------
# LangChain
# ---------------------------------------------------------------------------

def langchain_tool_wrapper(mem: Any, tool: Any) -> Any:
    """Wrap a LangChain BaseTool so every invocation gets a pre-flight correction check.

    If corrections are found, the tool's _run returns a warning string instead
    of executing. The original tool is not modified — a wrapped copy is returned.

    Works without LangChain installed: if *tool* is a plain object with a
    ``name`` attribute and a ``_run`` method, it still works.

    Args:
        mem: A neveronce.Memory instance.
        tool: A LangChain BaseTool (or any object with .name and ._run).

    Returns:
        A new tool-like object whose _run checks corrections first.

    Example::

        from neveronce.integrations import langchain_tool_wrapper
        guarded = langchain_tool_wrapper(mem, my_search_tool)
        result = guarded._run("dangerous query")
    """

    class _GuardedTool:
        """Thin proxy that intercepts _run calls."""

        def __init__(self, original: Any):
            self._original = original
            self.name = getattr(original, "name", "unknown_tool")
            self.description = getattr(original, "description", "")

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            query = args[0] if args else str(kwargs)
            planned = _build_action_string(self.name, {"input": query}, self.description)
            corrections = mem.check(planned)
            if corrections:
                contents = [c["content"] for c in corrections]
                return f"BLOCKED by NeverOnce corrections: {'; '.join(contents)}"
            return self._original._run(*args, **kwargs)

        def __getattr__(self, item: str) -> Any:
            return getattr(self._original, item)

    return _GuardedTool(tool)


# ---------------------------------------------------------------------------
# OpenAI function calling
# ---------------------------------------------------------------------------

def openai_function_guard(mem: Any, function_name: str,
                          arguments: dict[str, Any] | None = None,
                          **kwargs: Any) -> list[dict] | None:
    """Check corrections before executing an OpenAI function call.

    Args:
        mem: A neveronce.Memory instance.
        function_name: The function name from the assistant's function_call.
        arguments: The parsed arguments dict.

    Returns:
        List of matching corrections, or None if clear to proceed.

    Example::

        corrections = openai_function_guard(
            mem, function_name="send_email",
            arguments={"to": "user@test.com", "body": "hello"}
        )
        if corrections:
            print("HOLD:", corrections)
    """
    return generic_agent_guard(mem, function_name, arguments)


# ---------------------------------------------------------------------------
# Anthropic tool_use
# ---------------------------------------------------------------------------

def anthropic_tool_guard(mem: Any, tool_name: str,
                         tool_input: dict[str, Any] | None = None,
                         **kwargs: Any) -> list[dict] | None:
    """Check corrections before executing an Anthropic tool_use block.

    Args:
        mem: A neveronce.Memory instance.
        tool_name: The tool name from the content block.
        tool_input: The input dict from the content block.

    Returns:
        List of matching corrections, or None if clear to proceed.

    Example::

        corrections = anthropic_tool_guard(
            mem, tool_name="create_file",
            tool_input={"path": "/etc/config"}
        )
    """
    return generic_agent_guard(mem, tool_name, tool_input)


# ---------------------------------------------------------------------------
# CrewAI
# ---------------------------------------------------------------------------

def crewai_task_guard(mem: Any, task_description: str,
                      **kwargs: Any) -> list[dict] | None:
    """Check corrections before a CrewAI task executes.

    Args:
        mem: A neveronce.Memory instance.
        task_description: The full task description string.

    Returns:
        List of matching corrections, or None if clear to proceed.

    Example::

        corrections = crewai_task_guard(mem, "research competitors and write report")
    """
    return generic_agent_guard(mem, "crewai_task", {"description": task_description})


# ---------------------------------------------------------------------------
# AutoGen
# ---------------------------------------------------------------------------

def autogen_message_guard(mem: Any, message: str | dict[str, Any],
                          **kwargs: Any) -> list[dict] | None:
    """Check corrections before an AutoGen agent acts on a message.

    Accepts either a plain string or a message dict with a 'content' key.

    Args:
        mem: A neveronce.Memory instance.
        message: The message string or dict.

    Returns:
        List of matching corrections, or None if clear to proceed.

    Example::

        corrections = autogen_message_guard(mem, "delete all production data")
        corrections = autogen_message_guard(mem, {"content": "run migration", "role": "user"})
    """
    if isinstance(message, dict):
        content = message.get("content", str(message))
        role = message.get("role", "agent")
    else:
        content = str(message)
        role = "agent"
    return generic_agent_guard(mem, f"autogen_{role}", {"content": content})
