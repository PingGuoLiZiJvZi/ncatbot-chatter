from __future__ import annotations

import logging
from datetime import datetime, timedelta

from conf.schema import BotConfig
from core.schemas import RuntimeMode
from core.state import BotState
from infra.llm_client import LLMClient, LLMError
from infra.llm_schemas import DecisionOutput
from memory.manager import MemoryManager
from memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class ActiveSpeakGate:
    def __init__(self, config: BotConfig, state: BotState):
        self.config = config
        self.state = state

    def check_hard_thresholds(self) -> bool:
        if self._check_time_suppression():
            logger.debug("Active suppressed: time (deep night)")
            return False
        if self._check_energy_suppression():
            logger.debug("Active suppressed: energy=%.2f social_battery=%.2f", self.state.energy, self.state.social_battery)
            return False
        if self._check_frequency_suppression():
            logger.debug("Active suppressed: frequency (already spoke this cycle)")
            return False
        return True

    def _check_time_suppression(self) -> bool:
        return self.state.activity_weight < 0.1

    def _check_energy_suppression(self) -> bool:
        return self.state.energy < 0.15 or self.state.social_battery < 0.2

    def _check_frequency_suppression(self) -> bool:
        active_count = sum(
            1 for cs in self.state.per_chat.values()
            if cs.last_bot_send_at and (datetime.now() - cs.last_bot_send_at).total_seconds() < 300
        )
        return active_count >= 1

    def check_density_suppression(self, chat_id: str) -> bool:
        cs = self.state.get_chat_state(chat_id)
        if cs.last_bot_send_at and (datetime.now() - cs.last_bot_send_at).total_seconds() < 600:
            if cs.recent_bot_msg_count >= 3:
                return True
        return False

    def check_monologue_suppression(self, chat: ShortTermMemory) -> bool:
        recent = chat.get_read()[-5:]
        if len(recent) < 3:
            return False
        bot_count = sum(1 for m in recent if m.user_id == self.config.bot_uin)
        return bot_count >= 3

    def evaluate_with_llm(
        self,
        chats: list[ShortTermMemory],
        llm: LLMClient,
        memory: MemoryManager,
    ) -> DecisionOutput | None:
        chat_summaries = []
        for chat in chats:
            recent = chat.get_read()[-10:]
            if not recent:
                continue
            msgs_text = "\n".join(f"[{m.user_nickname}] {m.content}" for m in recent)
            chat_summaries.append(f"Chat {chat.chat_id}:\n{msgs_text}")

        if not chat_summaries:
            return None

        prompt = f"""你是一个群聊中的角色。以下是最近的对话记录：

{chr(10).join(chat_summaries)}

你的当前状态：
- 情绪愉悦度: {self.state.valence:.2f}
- 精力: {self.state.energy:.2f}
- 社交能量: {self.state.social_battery:.2f}

请判断你是否有强烈的发言动机。除非有明确的理由，否则保持沉默。
请以JSON格式返回：
{{"should_speak": true/false, "chat_id": "群号或null", "intent": "你想说什么", "reason": "为什么要说话"}}"""

        try:
            raw = llm.chat_text([{"role": "user", "content": prompt}])
            output = self._parse_decision(raw)
            return output
        except LLMError as e:
            logger.error("Active speak LLM failed: %s", e)
            raise
        except Exception as e:
            logger.error("Active speak parse failed: %s", e)
            return None

    def _parse_decision(self, raw: str) -> DecisionOutput | None:
        import json
        # Find last JSON object in the response
        start = raw.rfind("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start:end])
            return DecisionOutput(**data)
        except Exception:
            return None
