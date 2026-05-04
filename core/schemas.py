from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class Priority(str, Enum):
    P0 = "P0"  # private / @
    P1 = "P1"  # mentioned
    P2 = "P2"  # active


class ActionType(str, Enum):
    PASSIVE_REPLY = "PASSIVE_REPLY"
    ACTIVE_SPEAK = "ACTIVE_SPEAK"


class TickType(str, Enum):
    PASSIVE = "PASSIVE"
    ACTIVE = "ACTIVE"
    CONCENTRATE = "CONCENTRATE"


class RuntimeMode(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PASSIVE_ONLY = "PASSIVE_ONLY"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class BrakeDecision(str, Enum):
    ALLOW = "allow"
    CANCEL = "cancel"
    DELAY = "delay"
    MERGE = "merge"


class StateEventType(str, Enum):
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_FAILED = "MESSAGE_FAILED"
    LLM_FAILED = "LLM_FAILED"
    LLM_RECOVERED = "LLM_RECOVERED"
    MODE_CHANGED = "MODE_CHANGED"
    EMOTION_SHIFTED = "EMOTION_SHIFTED"


@dataclass
class ActionPlan:
    action_id: str
    action_type: ActionType
    priority: Priority
    chat_id: str
    chat_type: str
    trigger_message: str | None
    trigger_type: str
    reason: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GeneratedAction:
    plan: ActionPlan
    content: str
    llm_raw: str = ""
    mentions: list[str] = field(default_factory=list)
    reply_to: str | None = None


@dataclass
class DecisionResult:
    plans: list[ActionPlan] = field(default_factory=list)
    trigger_type: str = ""


@dataclass
class StateEvent:
    event_id: UUID = field(default_factory=uuid4)
    event_type: StateEventType = StateEventType.MESSAGE_SENT
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatState:
    chat_id: str
    last_bot_send_at: datetime | None = None
    recent_bot_msg_count: int = 0
    last_message_at: datetime | None = None
