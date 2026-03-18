"""Recal — The public API.

Usage:
    from recal import Memory

    mem = Memory("my_app")
    mem.store("user prefers dark mode", tags=["preference"])
    mem.correct("never use imperial units", context="unit conversion")
    results = mem.recall("what units should I use?")
"""

from __future__ import annotations

from pathlib import Path
from .db import RecalDB


class Memory:
    """Persistent, correctable AI memory.

    Args:
        name: Name for this memory store (creates ~/.recal/<name>.db)
        db_dir: Custom directory for the database file.
        namespace: Default namespace for organizing memories.
    """

    def __init__(self, name: str = "default", db_dir: str | Path | None = None,
                 namespace: str = "default"):
        self.db = RecalDB(name=name, db_dir=db_dir)
        self.namespace = namespace

    def store(self, content: str, *, tags: list[str] | None = None,
              context: str = "", importance: int = 5,
              namespace: str | None = None) -> int:
        """Store a memory. Returns the memory ID."""
        return self.db.insert(
            content=content,
            memory_type="general",
            tags=tags,
            context=context,
            importance=importance,
            namespace=namespace or self.namespace,
        )

    def correct(self, content: str, *, context: str = "",
                tags: list[str] | None = None,
                namespace: str | None = None) -> int:
        """Store a correction. Always importance 10. Always wins in recall.

        Corrections are the killer feature: they override normal memories
        so the AI never repeats the same mistake twice.
        """
        correction_tags = list(tags or [])
        if "correction" not in correction_tags:
            correction_tags.insert(0, "correction")
        return self.db.insert(
            content=content,
            memory_type="correction",
            tags=correction_tags,
            context=context,
            importance=10,
            namespace=namespace or self.namespace,
        )

    def recall(self, query: str, *, limit: int = 10,
               min_importance: int = 1,
               namespace: str | None = None) -> list[dict]:
        """Search memories by relevance. Corrections surface first.

        Returns list of memory dicts sorted by relevance, with corrections
        always ranked above regular memories at the same relevance level.
        """
        ns = namespace or self.namespace
        results = self.db.search(
            query=query,
            limit=limit * 2,  # fetch extra, then re-sort
            min_importance=min_importance,
            namespace=ns if ns != "default" else None,
        )

        # Corrections always float to the top
        corrections = [r for r in results if r["memory_type"] == "correction"]
        others = [r for r in results if r["memory_type"] != "correction"]
        combined = corrections + others

        return combined[:limit]

    def check(self, planned_action: str, *, namespace: str | None = None) -> list[dict]:
        """Check if any corrections apply before taking an action.

        This is the 'pre-flight check' — call it before doing something
        to see if there's a stored correction that should change your approach.
        Returns matching corrections only.
        """
        ns = namespace or self.namespace
        corrections = self.db.get_corrections(
            namespace=ns if ns != "default" else None, limit=50
        )
        if not corrections:
            return []

        # Simple keyword overlap matching
        action_words = set(planned_action.lower().split())
        matches = []
        for c in corrections:
            content_words = set(c["content"].lower().split())
            context_words = set(c.get("context", "").lower().split())
            all_words = content_words | context_words
            overlap = action_words & all_words
            # Need at least 2 significant words (>3 chars) matching
            significant = [w for w in overlap if len(w) > 3]
            if len(significant) >= 2:
                c["_match_score"] = len(significant)
                matches.append(c)

        matches.sort(key=lambda x: x["_match_score"], reverse=True)
        return matches[:5]

    def helped(self, memory_id: int, did_help: bool) -> None:
        """Mark whether a surfaced memory actually helped.

        This is the feedback loop. Memories that help get stronger.
        Memories that don't get weaker over time.
        """
        self.db.update_effectiveness(memory_id, did_help)

    def forget(self, memory_id: int) -> bool:
        """Delete a memory by ID. Returns True if it existed."""
        return self.db.delete(memory_id)

    def decay(self, surfaced_threshold: int = 5, decay_amount: int = 1) -> int:
        """Lower importance of unhelpful memories.

        Memories that have been surfaced >= threshold times but never
        marked as helpful get their importance reduced.
        Corrections are never decayed.

        Returns count of memories affected.
        """
        return self.db.decay(surfaced_threshold, decay_amount)

    def stats(self) -> dict:
        """Get memory store statistics."""
        return self.db.stats()

    def close(self):
        """Close the database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        s = self.stats()
        return f"Memory(total={s['total']}, corrections={s['corrections']})"
