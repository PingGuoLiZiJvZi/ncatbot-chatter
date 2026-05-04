from __future__ import annotations

import logging
import sqlite3
import threading

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS entity_profile (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id    TEXT NOT NULL UNIQUE,
    entity_type  TEXT NOT NULL DEFAULT 'user',
    display_name TEXT NOT NULL DEFAULT '',
    summary      TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_entity_id ON entity_profile(entity_id);
"""


class EntityProfile:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def get(self, entity_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT entity_id, entity_type, display_name, summary FROM entity_profile WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
        if row is None:
            return None
        return {"entity_id": row[0], "entity_type": row[1], "display_name": row[2], "summary": row[3]}

    def upsert(
        self,
        entity_id: str,
        entity_type: str = "user",
        display_name: str = "",
        summary: str = "",
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO entity_profile (entity_id, entity_type, display_name, summary, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(entity_id) DO UPDATE SET
                     entity_type = excluded.entity_type,
                     display_name = CASE WHEN excluded.display_name = '' THEN entity_profile.display_name ELSE excluded.display_name END,
                     summary = CASE WHEN excluded.summary = '' THEN entity_profile.summary ELSE excluded.summary END,
                     updated_at = datetime('now')""",
                (entity_id, entity_type, display_name, summary),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
