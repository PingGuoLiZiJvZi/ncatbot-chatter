from __future__ import annotations

import logging
import sqlite3
import threading

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS relationship (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a   TEXT NOT NULL,
    entity_b   TEXT NOT NULL,
    rel_type   TEXT NOT NULL DEFAULT 'acquaintance',
    intimacy   REAL NOT NULL DEFAULT 0.0,
    note       TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_a, entity_b)
);
CREATE INDEX IF NOT EXISTS idx_rel_a ON relationship(entity_a);
CREATE INDEX IF NOT EXISTS idx_rel_b ON relationship(entity_b);
"""


class RelationshipGraph:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def get(self, entity_a: str, entity_b: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT entity_a, entity_b, rel_type, intimacy, note FROM relationship WHERE entity_a = ? AND entity_b = ?",
                (entity_a, entity_b),
            ).fetchone()
        if row is None:
            return None
        return {"entity_a": row[0], "entity_b": row[1], "rel_type": row[2], "intimacy": row[3], "note": row[4]}

    def upsert(
        self,
        entity_a: str,
        entity_b: str,
        rel_type: str = "acquaintance",
        intimacy: float = 0.0,
        note: str = "",
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO relationship (entity_a, entity_b, rel_type, intimacy, note, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(entity_a, entity_b) DO UPDATE SET
                     rel_type = excluded.rel_type,
                     intimacy = excluded.intimacy,
                     note = excluded.note,
                     updated_at = datetime('now')""",
                (entity_a, entity_b, rel_type, intimacy, note),
            )
            self._conn.commit()

    def get_all_for(self, entity: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT entity_a, entity_b, rel_type, intimacy, note FROM relationship WHERE entity_a = ? OR entity_b = ?",
                (entity, entity),
            ).fetchall()
        return [
            {"entity_a": r[0], "entity_b": r[1], "rel_type": r[2], "intimacy": r[3], "note": r[4]}
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
