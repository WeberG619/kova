"""Recal MCP Server — Plug memory into any MCP-compatible AI.

Run:
    python -m recal.server
    python -m recal.server --name my_app --port 0

Or add to your MCP config:
    {
        "mcpServers": {
            "recal": {
                "command": "python",
                "args": ["-m", "recal.server"]
            }
        }
    }
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "MCP server requires the 'mcp' package.\n"
        "Install it with: pip install recal[mcp]\n"
        "Or: pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

from .memory import Memory

# Will be initialized on startup
_mem: Memory | None = None


def _get_mem() -> Memory:
    global _mem
    if _mem is None:
        _mem = Memory("recal")
    return _mem


mcp = FastMCP(
    "recal",
    version="0.1.0",
    description="Persistent, correctable memory for AI. The memory layer that learns from mistakes.",
)


@mcp.tool()
def store(content: str, tags: str = "", context: str = "",
          importance: int = 5, namespace: str = "default") -> str:
    """Store a memory.

    Args:
        content: The memory content to store.
        tags: Comma-separated tags (e.g. "preference,ui,dark-mode").
        context: When/where this memory applies.
        importance: 1-10, how important this memory is.
        namespace: Namespace for organizing memories.
    """
    mem = _get_mem()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    mid = mem.store(content, tags=tag_list, context=context,
                    importance=importance, namespace=namespace)
    return f"Stored memory #{mid}"


@mcp.tool()
def correct(content: str, context: str = "", tags: str = "",
            namespace: str = "default") -> str:
    """Store a correction. Always maximum importance. Always surfaces first.

    Use this when the AI made a mistake and you want to prevent it from
    happening again. Corrections override normal memories.

    Args:
        content: What the correct behavior/answer should be.
        context: When/where this correction applies.
        tags: Comma-separated tags.
        namespace: Namespace for organizing memories.
    """
    mem = _get_mem()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    mid = mem.correct(content, context=context, tags=tag_list,
                      namespace=namespace)
    return f"Stored correction #{mid} (importance: 10, always surfaces first)"


@mcp.tool()
def recall(query: str, limit: int = 10, namespace: str = "default") -> str:
    """Search memories by relevance. Corrections surface first.

    Args:
        query: What to search for.
        limit: Max results to return.
        namespace: Filter by namespace.
    """
    mem = _get_mem()
    results = mem.recall(query, limit=limit, namespace=namespace)
    if not results:
        return "No memories found."

    lines = []
    for r in results:
        marker = " [CORRECTION]" if r["memory_type"] == "correction" else ""
        tags = json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"]
        tag_str = f" ({', '.join(tags)})" if tags else ""
        lines.append(
            f"#{r['id']}{marker} [importance:{r['importance']}]{tag_str}\n"
            f"  {r['content']}"
        )
    return "\n\n".join(lines)


@mcp.tool()
def check(planned_action: str, namespace: str = "default") -> str:
    """Pre-flight check: see if any corrections apply before taking an action.

    Call this before doing something to see if there's a stored correction
    that should change your approach.

    Args:
        planned_action: Describe what you're about to do.
        namespace: Filter by namespace.
    """
    mem = _get_mem()
    matches = mem.check(planned_action, namespace=namespace)
    if not matches:
        return "No corrections apply. Proceed."

    lines = ["CORRECTIONS APPLY — review before proceeding:\n"]
    for m in matches:
        lines.append(f"  #{m['id']}: {m['content']}")
        if m.get("context"):
            lines.append(f"    Context: {m['context']}")
    return "\n".join(lines)


@mcp.tool()
def helped(memory_id: int, did_help: bool) -> str:
    """Mark whether a surfaced memory actually helped.

    This feedback loop is what makes Recal learn.
    Helpful memories get stronger. Unhelpful ones decay.

    Args:
        memory_id: The memory ID (from recall results).
        did_help: True if the memory was useful, False if not.
    """
    mem = _get_mem()
    mem.helped(memory_id, did_help)
    return f"Memory #{memory_id} marked as {'helpful' if did_help else 'not helpful'}"


@mcp.tool()
def forget(memory_id: int) -> str:
    """Delete a memory by ID.

    Args:
        memory_id: The memory to delete.
    """
    mem = _get_mem()
    if mem.forget(memory_id):
        return f"Memory #{memory_id} deleted."
    return f"Memory #{memory_id} not found."


@mcp.tool()
def stats() -> str:
    """Get memory store statistics."""
    mem = _get_mem()
    s = mem.stats()
    return (
        f"Total memories: {s['total']}\n"
        f"Corrections: {s['corrections']}\n"
        f"Avg importance: {s['avg_importance']:.1f}\n"
        f"Avg effectiveness: {(s['avg_effectiveness'] or 0):.2f}"
    )


def main():
    parser = argparse.ArgumentParser(description="Recal MCP Server")
    parser.add_argument("--name", default="recal",
                        help="Memory store name (default: recal)")
    parser.add_argument("--namespace", default="default",
                        help="Default namespace")
    args = parser.parse_args()

    global _mem
    _mem = Memory(name=args.name, namespace=args.namespace)

    mcp.run()


if __name__ == "__main__":
    main()
