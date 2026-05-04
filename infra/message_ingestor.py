from __future__ import annotations

import logging
import queue
from datetime import datetime
from typing import Any

from memory.schemas import Message
from memory.manager import MemoryManager
from infra.raw_message_log import RawMessageLog

logger = logging.getLogger(__name__)


class MessageIngestor:
    def __init__(self, q: queue.Queue, memory: MemoryManager, raw_log: RawMessageLog):
        self._queue = q
        self.memory = memory
        self.raw_log = raw_log

    def drain(self, max_items: int = 50) -> int:
        count = 0
        for _ in range(max_items):
            try:
                raw_event = self._queue.get_nowait()
            except queue.Empty:
                break
            msg = self._parse(raw_event)
            if msg is None:
                logger.warning("Failed to parse raw event: %s", type(raw_event).__name__)
                continue
            if not self.raw_log.insert_if_new(msg.message_id):
                logger.debug("Duplicate message_id=%s, skipping", msg.message_id)
                continue
            self.memory.add_message(msg)
            count += 1
            logger.info("Ingested message: chat=%s user=%s content=%s", msg.chat_id, msg.user_id, msg.content[:30])
        return count

    def _parse(self, raw_event: Any) -> Message | None:
        try:
            event_type = type(raw_event).__name__
            if event_type in ("GroupMessage", "GroupMessageEvent"):
                return self._parse_group(raw_event)
            elif event_type in ("PrivateMessage", "PrivateMessageEvent"):
                return self._parse_private(raw_event)
            else:
                # Try duck-typing: check for common attributes
                if hasattr(raw_event, "group_id"):
                    return self._parse_group(raw_event)
                elif hasattr(raw_event, "user_id") and not hasattr(raw_event, "group_id"):
                    return self._parse_private(raw_event)
                logger.warning("Unknown event type: %s", event_type)
                return None
        except Exception as e:
            logger.error("Failed to parse message: %s", e, exc_info=True)
            return None

    def _parse_group(self, event: Any) -> Message | None:
        message_id = str(getattr(event, "message_id", ""))
        group_id = str(getattr(event, "group_id", ""))
        user_id = str(getattr(event, "user_id", ""))

        content = self._extract_content(event)
        if not content:
            return None

        sender = getattr(event, "sender", None)
        if isinstance(sender, dict):
            user_nickname = str(sender.get("nickname", ""))
            group_nickname = str(sender.get("card", ""))
        else:
            user_nickname = str(getattr(sender, "nickname", "") or "")
            group_nickname = str(getattr(sender, "card", "") or "")

        return Message(
            message_id=message_id,
            chat_type="group",
            chat_id=group_id,
            user_id=user_id,
            user_nickname=user_nickname,
            group_nickname=group_nickname,
            content=content,
            timestamp=datetime.now(),
        )

    def _parse_private(self, event: Any) -> Message | None:
        message_id = str(getattr(event, "message_id", ""))
        user_id = str(getattr(event, "user_id", ""))

        content = self._extract_content(event)
        if not content:
            return None

        sender = getattr(event, "sender", None)
        if isinstance(sender, dict):
            user_nickname = str(sender.get("nickname", ""))
        else:
            user_nickname = str(getattr(sender, "nickname", "") or "")

        return Message(
            message_id=message_id,
            chat_type="private",
            chat_id=user_id,
            user_id=user_id,
            user_nickname=user_nickname,
            group_nickname="",
            content=content,
            timestamp=datetime.now(),
        )

    @staticmethod
    def _extract_content(event: Any) -> str:
        """Extract text content from an event, preferring raw_message."""
        raw = getattr(event, "raw_message", None)
        if raw and isinstance(raw, str):
            return raw.strip()
        # Fallback: try to extract from message segments
        return MessageIngestor._extract_text(getattr(event, "message", []))

    @staticmethod
    def _extract_text(raw_message: Any) -> str:
        if isinstance(raw_message, str):
            return raw_message
        if isinstance(raw_message, list):
            parts = []
            for seg in raw_message:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    parts.append(seg.get("data", {}).get("text", ""))
            return "".join(parts).strip()
        return ""
