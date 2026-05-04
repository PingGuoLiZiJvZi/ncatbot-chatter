from __future__ import annotations

import logging
from conf.schema import BotConfig
from core.schemas import ActionPlan, ActionType, Priority
from memory.schemas import Message
from memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class PassiveReplyJudge:
    def __init__(self, config: BotConfig):
        self.bot_uin = config.bot_uin

    def evaluate(self, chats: list[ShortTermMemory]) -> list[ActionPlan]:
        plans = []
        for chat in chats:
            unread = chat.consume_unread()
            for msg in unread:
                plan = self._check_message(msg)
                if plan:
                    plans.append(plan)
        return plans

    def _check_message(self, msg: Message) -> ActionPlan | None:
        if self._is_at(msg):
            return self._make_plan(msg, Priority.P0, "at_bot")
        if msg.chat_type == "private":
            return self._make_plan(msg, Priority.P0, "private_message")
        if self._is_mentioned(msg):
            return self._make_plan(msg, Priority.P1, "mentioned")
        return None

    def _is_at(self, msg: Message) -> bool:
        if msg.chat_type == "private":
            return False
        return f"@{self.bot_uin}" in msg.content or f"[CQ:at,qq={self.bot_uin}]" in msg.content

    def _is_mentioned(self, msg: Message) -> bool:
        return self.bot_uin in msg.content

    def _make_plan(self, msg: Message, priority: Priority, reason: str) -> ActionPlan:
        return ActionPlan(
            action_id=f"passive-{msg.message_id}",
            action_type=ActionType.PASSIVE_REPLY,
            priority=priority,
            chat_id=msg.chat_id,
            chat_type=msg.chat_type,
            trigger_message=msg.content,
            trigger_type="passive_tick",
            reason=reason,
        )
