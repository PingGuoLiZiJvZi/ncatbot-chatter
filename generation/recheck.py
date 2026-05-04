from __future__ import annotations

import logging

from core.schemas import GeneratedAction
from infra.llm_client import LLMClient, LLMError
from memory.manager import MemoryManager

logger = logging.getLogger(__name__)

_RECHECK_PROMPT = (
    "你是一个判断助手。你需要根据最新的聊天记录，判断一条计划中的回复是否仍然需要发送。\n\n"
    "判断标准：\n"
    "- 如果在触发消息之后，已经有人替你回答了类似的内容，则不需要回复\n"
    "- 如果话题已经转移，原来的回复不再相关，则不需要回复\n"
    "- 如果触发消息之后有新的重要消息需要优先处理，则不需要回复原来的\n"
    "- 其他情况，仍然需要回复\n\n"
    "请只回复 \"need_reply\" 或 \"no_need_reply\"，不要输出其他内容。"
)


class RecheckService:
    def __init__(self, llm_flash: LLMClient, memory: MemoryManager):
        self.llm = llm_flash
        self.memory = memory

    def filter_actions(self, actions: list[GeneratedAction]) -> list[GeneratedAction]:
        if not actions:
            return []

        kept: list[GeneratedAction] = []
        for action in actions:
            if self._should_reply(action):
                kept.append(action)
            else:
                logger.info(
                    "Recheck: dropping %s (chat=%s) — reply no longer needed",
                    action.plan.action_id, action.plan.chat_id,
                )
        return kept

    def _should_reply(self, action: GeneratedAction) -> bool:
        chat = self.memory.get_chat(action.plan.chat_id)
        if chat is None:
            return True

        recent = chat.get_read()
        if not recent:
            return True

        history_lines: list[str] = []
        for msg in recent[-20:]:
            history_lines.append(f"[{msg.user_nickname}] {msg.content}")
        history_text = "\n".join(history_lines)

        user_msg = (
            f"聊天记录：\n{history_text}\n\n"
            f"计划回复（针对触发消息 \"{action.plan.trigger_message}\"）：\n"
            f"{action.content}\n\n"
            f"这条回复是否仍然需要发送？"
        )

        messages = [
            {"role": "system", "content": _RECHECK_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        try:
            result = self.llm.chat_text(messages).strip().lower()
            if "no_need" in result:
                return False
            return True
        except LLMError as e:
            logger.warning("Recheck LLM failed for %s: %s — defaulting to keep", action.plan.action_id, e)
            return True
