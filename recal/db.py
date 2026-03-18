"""Recal — SQLite + FTS5 storage engine.

Zero dependencies. Just Python's built-in sqlite3.
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timezone


DEFAULT_DIR = Path.home() / ".recal"

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'general',
    tags TEXT DEFAULT '[]',
    context TEXT DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 5,
    times_surfaced INTEGER DEFAULT 0,
    times_helped INTEGER DEFAULT 0,
    effectiveness REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    namespace TEXT DEFAULT 'default'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, tags, context, namespace,
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags, context, namespace)
    VALUES (new.id, new.content, new.tags, new.context, new.namespace);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    UPDATE memories_fts SET
        content = new.content,
        tags = new.tags,
        context = new.context,
        namespace = new.namespace
    WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    DELETE FROM memories_fts WHERE rowid = old.id;
END;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


class RecalDB:
    """Lightweight SQLite + FTS5 memory store."""

    def __init__(self, name: str = "default", db_dir: str | Path | None = None):
        dir_path = Path(db_dir) if db_dir else DEFAULT_DIR
        dir_path.mkdir(parents=True, exist_ok=True)
        db_path = dir_path / f"{name}.db"
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        # Check if already initialized
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
        )
        if cursor.fetchone():
            return
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self.conn.commit()

    def insert(self, content: str, memory_type: str = "general",
               tags: list[str] | None = None, context: str = "",
               importance: int = 5, namespace: str = "default") -> int:
        now = _now()
        cursor = self.conn.execute(
            """INSERT INTO memories
               (content, memory_type, tags, context, importance,
                created_at, accessed_at, namespace)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (content, memory_type, json.dumps(tags or []), context,
             min(max(importance, 1), 10), now, now, namespace),
        )
        self.conn.commit()
        return cursor.lastrowid

    def search(self, query: str, limit: int = 10,
               memory_type: str | None = None,
               min_importance: int = 1,
               namespace: str | None = None) -> list[dict]:
        """Full-text search with BM25 ranking."""
        # Escape FTS5 special characters
        safe_query = query.replace('"', '""')
        tokens = safe_query.split()
        if not tokens:
            return []
        # Match any token (OR), let BM25 rank
        fts_query = " OR ".join(f'"{t}"' for t in tokens)

        sql = """
            SELECT m.*, bm25(memories_fts) AS rank
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.rowid
            WHERE memories_fts MATCH ?
              AND m.importance >= ?
        """
        params: list = [fts_query, min_importance]

        if memory_type:
            sql += " AND m.memory_type = ?"
            params.append(memory_type)
        if namespace:
            sql += " AND m.namespace = ?"
            params.append(namespace)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        # Update access tracking
        for row in rows:
            self.conn.execute(
                "UPDATE memories SET accessed_at = ?, times_surfaced = times_surfaced + 1 WHERE id = ?",
                (_now(), row["id"]),
            )
        self.conn.commit()
        return [dict(r) for r in rows]

    def get(self, memory_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_effectiveness(self, memory_id: int, helped: bool):
        mem = self.get(memory_id)
        if not mem:
            return
        surfaced = mem["times_surfaced"]
        helped_count = mem["times_helped"] + (1 if helped else 0)
        effectiveness = helped_count / max(surfaced, 1)
        self.conn.execute(
            """UPDATE memories
               SET times_helped = ?, effectiveness = ?, accessed_at = ?
               WHERE id = ?""",
            (helped_count, effectiveness, _now(), memory_id),
        )
        self.conn.commit()

    def decay(self, surfaced_threshold: int = 5, decay_amount: int = 1) -> int:
        """Lower importance of memories that get surfaced but never help."""
        cursor = self.conn.execute(
            """UPDATE memories
               SET importance = MAX(1, importance - ?)
               WHERE times_surfaced >= ? AND times_helped = 0
                 AND memory_type != 'correction'
               RETURNING id""",
            (decay_amount, surfaced_threshold),
        )
        count = len(cursor.fetchall())
        self.conn.commit()
        return count

    def delete(self, memory_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_corrections(self, namespace: str | None = None,
                        limit: int = 10) -> list[dict]:
        """Get corrections, highest importance first."""
        sql = "SELECT * FROM memories WHERE memory_type = 'correction'"
        params: list = []
        if namespace:
            sql += " AND namespace = ?"
            params.append(namespace)
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN memory_type='correction' THEN 1 ELSE 0 END) as corrections,
                 AVG(importance) as avg_importance,
                 AVG(effectiveness) as avg_effectiveness
               FROM memories"""
        ).fetchone()
        return dict(row)

    def close(self):
        self.conn.close()
