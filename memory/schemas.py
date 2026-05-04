from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    EVENT = "event"
    FACT = "fact"
    IMPRESSION = "impression"
    PLAN = "plan"


@dataclass
class Message:
    message_id: str
    chat_type: str  # "private" | "group"
    chat_id: str
    user_id: str
    user_nickname: str
    group_nickname: str
    content: str
    timestamp: datetime


@dataclass
class SelfMessage:
    chat_type: str
    chat_id: str
    content: str
    timestamp: datetime
    action_id: str


@dataclass
class MemoryEntry:
    id: int | None = None
    memory_type: MemoryType = MemoryType.EVENT
    chat_type: str = ""
    chat_id: str = ""
    timestamp: str = ""
    importance: int = 5
    confidence: float = 1.0
    summary: str = ""
    keywords: str = ""
    source_message_ids: str = ""
    access_count: int = 0
    expires_at: str | None = None
    is_active: int = 1
    created_at: str = ""


@dataclass
class MemoryContext:
    entries: list[MemoryEntry] = field(default_factory=list)
    query: str = ""
    chat_id: str = ""
