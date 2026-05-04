from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime

from core.schemas import ActionPlan, GeneratedAction
from infra.bot_adapter import SendResult

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS action_log (
    action_id         TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'planned',
    chat_type         TEXT NOT NULL,
    chat_id           TEXT NOT NULL,
    trigger_type      TEXT,
    priority          TEXT,
    reason            TEXT,
    content           TEXT,
    llm_raw           TEXT,
    send_status       TEXT,
    send_error        TEXT,
    latency_ms        INTEGER,
    cancelled_reason  TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(status IN ('planned', 'generated', 'scheduled', 'sending', 'sent', 'cancelled', 'failed'))
);
CREATE INDEX IF NOT EXISTS idx_action_status ON action_log(status);
CREATE INDEX IF NOT EXISTS idx_action_chat ON action_log(chat_type, chat_id);
"""

_VALID_STATUSES = {"planned", "generated", "scheduled", "sending", "sent", "cancelled", "failed"}


class ActionLog:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

    def record_planned(self, plans: list[ActionPlan]) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            for p in plans:
                self._conn.execute(
                    """INSERT OR IGNORE INTO action_log
                       (action_id, created_at, status, chat_type, chat_id, trigger_type, priority, reason)
                       VALUES (?, ?, 'planned', ?, ?, ?, ?, ?)""",
                    (p.action_id, now, p.chat_type, p.chat_id, p.trigger_type, p.priority.value, p.reason),
                )
            self._conn.commit()

    def record_generated(self, generated: list[GeneratedAction]) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            for g in generated:
                self._conn.execute(
                    """UPDATE action_log
                       SET status = 'generated', content = ?, llm_raw = ?, updated_at = ?
                       WHERE action_id = ? AND status = 'planned'""",
                    (g.content, g.llm_raw, now, g.plan.action_id),
                )
            self._conn.commit()

    def record_scheduled(self, generated: list[GeneratedAction]) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            for g in generated:
                self._conn.execute(
                    """UPDATE action_log
                       SET status = 'scheduled', updated_at = ?
                       WHERE action_id = ? AND status = 'generated'""",
                    (now, g.plan.action_id),
                )
            self._conn.commit()

    def mark_as_sending(self, action_id: str) -> bool:
        now = datetime.now().isoformat()
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE action_log
                   SET status = 'sending', updated_at = ?
                   WHERE action_id = ?
                     AND status IN ('planned', 'generated', 'scheduled')""",
                (now, action_id),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def record_send_result(self, result: SendResult) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                """UPDATE action_log
                   SET status = 'sent', send_status = ?, send_error = ?, latency_ms = ?, updated_at = ?
                   WHERE action_id = ? AND status = 'sending'""",
                (result.status.value, result.error, result.latency_ms, now, result.action_id),
            )
            self._conn.commit()

    def record(self, plan: ActionPlan, status: str, reason: str = "") -> None:
        now = datetime.now().isoformat()
        with self._lock:
            if status == "cancelled":
                self._conn.execute(
                    """UPDATE action_log
                       SET status = 'cancelled', cancelled_reason = ?, updated_at = ?
                       WHERE action_id = ? AND status NOT IN ('sent', 'cancelled', 'failed')""",
                    (reason, now, plan.action_id),
                )
            elif status == "failed":
                self._conn.execute(
                    """UPDATE action_log
                       SET status = 'failed', send_error = ?, updated_at = ?
                       WHERE action_id = ? AND status NOT IN ('sent', 'cancelled', 'failed')""",
                    (reason, now, plan.action_id),
                )
            else:
                if status in _VALID_STATUSES:
                    self._conn.execute(
                        """UPDATE action_log
                           SET status = ?, updated_at = ?
                           WHERE action_id = ?""",
                        (status, now, plan.action_id),
                    )
            self._conn.commit()

    def record_batch(self, plans: list[ActionPlan], status: str, reason: str = "") -> None:
        for p in plans:
            self.record(p, status, reason)

    def get_status(self, action_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM action_log WHERE action_id = ?", (action_id,)
            ).fetchone()
            return row[0] if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
