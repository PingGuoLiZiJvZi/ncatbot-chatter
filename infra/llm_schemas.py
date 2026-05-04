from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from memory.schemas import MemoryType


class DecisionOutput(BaseModel):
    should_speak: bool
    chat_id: Optional[str] = None
    intent: Optional[str] = None
    reason: Optional[str] = None


class ResponseAction(BaseModel):
    content: str
    mention_user_id: Optional[str] = None
    reply_to_message_id: Optional[str] = None


class ResponseOutput(BaseModel):
    actions: list[ResponseAction]


class ConcentrateItem(BaseModel):
    memory_type: MemoryType
    summary: str
    importance: int
    confidence: float
    keywords: list[str]
    source_message_ids: list[str]
    expires_at: Optional[datetime] = None


class ConcentrateOutput(BaseModel):
    entries: list[ConcentrateItem]
