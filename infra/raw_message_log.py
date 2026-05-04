from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS raw_message_log (
    message_id  TEXT PRIMARY KEY,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_raw_msg_received ON raw_message_log(received_at);
"""


class RawMessageLog:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def insert_if_new(self, message_id: str) -> bool:
        try:
            with self._lock:
                before = self._conn.total_changes
                self._conn.execute(
                    "INSERT OR IGNORE INTO raw_message_log (message_id) VALUES (?)",
                    (message_id,),
                )
                self._conn.commit()
                return self._conn.total_changes > before
        except sqlite3.Error as e:
            logger.error("RawMessageLog insert error: %s", e)
            return False

    def cleanup(self, ttl_days: int) -> int:
        cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM raw_message_log WHERE received_at < ?", (cutoff,)
            )
            self._conn.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
