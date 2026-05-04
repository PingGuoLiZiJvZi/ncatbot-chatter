from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime

from memory.schemas import MemoryContext, MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS memory_entry (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type        TEXT    NOT NULL DEFAULT 'event',
    chat_type          TEXT    NOT NULL,
    chat_id            TEXT    NOT NULL,
    timestamp          TEXT    NOT NULL,
    importance         INTEGER NOT NULL DEFAULT 5,
    confidence         REAL    NOT NULL DEFAULT 1.0,
    summary            TEXT    NOT NULL,
    keywords           TEXT,
    source_message_ids TEXT,
    access_count       INTEGER NOT NULL DEFAULT 0,
    expires_at         TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_memory_chat ON memory_entry(chat_type, chat_id);
CREATE INDEX IF NOT EXISTS idx_memory_active ON memory_entry(is_active, chat_id);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON memory_entry(expires_at) WHERE expires_at IS NOT NULL;
"""


class LongTermMemory:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def add(self, entry: MemoryEntry) -> int:
        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO memory_entry
                   (memory_type, chat_type, chat_id, timestamp, importance, confidence,
                    summary, keywords, source_message_ids, expires_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.memory_type.value,
                    entry.chat_type,
                    entry.chat_id,
                    entry.timestamp,
                    entry.importance,
                    entry.confidence,
                    entry.summary,
                    entry.keywords,
                    entry.source_message_ids,
                    entry.expires_at,
                    entry.is_active,
                ),
            )
            self._conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def search(
        self,
        query: str,
        chat_id: str | None = None,
        limit: int = 5,
        include_inactive: bool = False,
    ) -> list[MemoryEntry]:
        conditions = []
        params: list = []

        if not include_inactive:
            conditions.append("is_active = 1")

        if chat_id is not None:
            conditions.append("chat_id = ?")
            params.append(chat_id)

        if query:
            conditions.append("(summary LIKE ? OR keywords LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"""SELECT id, memory_type, chat_type, chat_id, timestamp,
                           importance, confidence, summary, keywords,
                           source_message_ids, access_count, expires_at, is_active, created_at
                    FROM memory_entry {where}
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?""",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def mark_accessed(self, entry_ids: list[int]) -> None:
        if not entry_ids:
            return
        with self._lock:
            placeholders = ",".join("?" for _ in entry_ids)
            self._conn.execute(
                f"UPDATE memory_entry SET access_count = access_count + 1 WHERE id IN ({placeholders})",
                entry_ids,
            )
            self._conn.commit()

    def expire_old(self, now: datetime | None = None, archive: bool = True) -> int:
        if now is None:
            now = datetime.now()
        now_str = now.isoformat()
        with self._lock:
            if archive:
                cursor = self._conn.execute(
                    "UPDATE memory_entry SET is_active = 0 WHERE expires_at < ? AND is_active = 1",
                    (now_str,),
                )
            else:
                cursor = self._conn.execute(
                    "DELETE FROM memory_entry WHERE expires_at < ? AND is_active = 1",
                    (now_str,),
                )
            self._conn.commit()
            return cursor.rowcount

    def merge_similar(self, entry: MemoryEntry) -> int | None:
        if not entry.keywords:
            return None
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, summary, keywords, importance, access_count
                   FROM memory_entry
                   WHERE chat_id = ? AND is_active = 1 AND memory_type = ?
                     AND id != COALESCE(?, -1)
                   ORDER BY created_at DESC LIMIT 50""",
                (entry.chat_id, entry.memory_type.value, entry.id),
            ).fetchall()

        for row in rows:
            row_id, row_summary, row_keywords, row_importance, row_access = row
            entry_kws = set(entry.keywords.split(",")) if entry.keywords else set()
            row_kws = set(row_keywords.split(",")) if row_keywords else set()
            if not entry_kws or not row_kws:
                continue
            overlap = len(entry_kws & row_kws) / max(len(entry_kws), 1)
            if overlap >= 0.5:
                merged_importance = max(entry.importance, row_importance)
                merged_summary = f"{row_summary}; {entry.summary}" if entry.summary not in row_summary else row_summary
                merged_keywords = ",".join(sorted(entry_kws | row_kws))
                with self._lock:
                    self._conn.execute(
                        """UPDATE memory_entry
                           SET summary = ?, keywords = ?, importance = ?, access_count = access_count + ?
                           WHERE id = ?""",
                        (merged_summary, merged_keywords, merged_importance, entry.access_count, row_id),
                    )
                    self._conn.commit()
                return row_id
        return None

    def get_context(self, chat_id: str, query: str) -> MemoryContext:
        entries = self.search(query, chat_id=chat_id, limit=5)
        if entries:
            ids = [e.id for e in entries if e.id is not None]
            self.mark_accessed(ids)
            for e in entries:
                e.access_count += 1
        return MemoryContext(entries=entries, query=query, chat_id=chat_id)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_entry(row: tuple) -> MemoryEntry:
        return MemoryEntry(
            id=row[0],
            memory_type=MemoryType(row[1]),
            chat_type=row[2],
            chat_id=row[3],
            timestamp=row[4],
            importance=row[5],
            confidence=row[6],
            summary=row[7],
            keywords=row[8] or "",
            source_message_ids=row[9] or "",
            access_count=row[10],
            expires_at=row[11],
            is_active=row[12],
            created_at=row[13] or "",
        )
