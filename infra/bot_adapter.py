from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SendStatus(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    CONTENT_FILTERED = "CONTENT_FILTERED"
    UNKNOWN = "UNKNOWN"


@dataclass
class SendResult:
    action_id: str
    status: SendStatus
    error: str | None = None
    latency_ms: int = 0


class BotAdapter:
    def __init__(self, bot: Any | None = None):
        self._bot = bot

    def send_group_msg(self, group_id: str, content: str, **kwargs: Any) -> SendResult:
        action_id = kwargs.pop("action_id", "")
        t0 = time.monotonic()
        try:
            if self._bot is None:
                raise RuntimeError("No bot instance configured")
            self._bot.send_group_msg_sync(int(group_id), content)
            latency = int((time.monotonic() - t0) * 1000)
            logger.info("Sent group msg to %s latency=%dms", group_id, latency)
            return SendResult(action_id=action_id, status=SendStatus.SENT, latency_ms=latency)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error("Failed to send group msg to %s: %s", group_id, e)
            status = SendStatus.FAILED
            return SendResult(action_id=action_id, status=status, error=str(e), latency_ms=latency)

    def send_private_msg(self, user_id: str, content: str, **kwargs: Any) -> SendResult:
        action_id = kwargs.pop("action_id", "")
        t0 = time.monotonic()
        try:
            if self._bot is None:
                raise RuntimeError("No bot instance configured")
            self._bot.send_private_msg_sync(int(user_id), content)
            latency = int((time.monotonic() - t0) * 1000)
            logger.info("Sent private msg to %s latency=%dms", user_id, latency)
            return SendResult(action_id=action_id, status=SendStatus.SENT, latency_ms=latency)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error("Failed to send private msg to %s: %s", user_id, e)
            return SendResult(action_id=action_id, status=SendStatus.FAILED, error=str(e), latency_ms=latency)

    def start(self) -> None:
        logger.info("BotAdapter started")

    def stop(self) -> None:
        logger.info("BotAdapter stopped")
