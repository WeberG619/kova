"""NeverOnce — Persistent, correctable memory for AI.

The memory layer that learns from mistakes.
"""

__version__ = "0.2.0"

from .memory import Memory
from .db import NeverOnceDB
from .guard import guard, GuardedAgent, ActionLog, CorrectionWarning, guard_tool_call

__all__ = [
    "Memory",
    "NeverOnceDB",
    "guard",
    "GuardedAgent",
    "ActionLog",
    "CorrectionWarning",
    "guard_tool_call",
]
