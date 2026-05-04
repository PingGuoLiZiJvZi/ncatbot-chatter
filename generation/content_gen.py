from __future__ import annotations

import json
import logging

from core.schemas import ActionPlan, GeneratedAction
from generation.formatter import ResponseFormatter
from infra.llm_client import LLMClient, LLMError
from infra.llm_schemas import ResponseAction, ResponseOutput

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, llm: LLMClient, formatter: ResponseFormatter):
        self.llm = llm
        self.formatter = formatter

    def generate(self, plans: list[ActionPlan]) -> list[GeneratedAction]:
        results = []
        for plan in plans:
            try:
                action = self._generate_one(plan)
                if action:
                    results.append(action)
            except LLMError:
                raise
            except Exception as e:
                logger.error("Content generation failed for %s: %s", plan.action_id, e)
        return results

    def _generate_one(self, plan: ActionPlan) -> GeneratedAction | None:
        system = self.formatter.format_system_prompt()
        response_prompt = self.formatter.format_response_prompt()

        user_msg = f"触发消息：{plan.trigger_message or '(主动发言)'}\n回复原因：{plan.reason}"
        if response_prompt:
            user_msg = f"{response_prompt}\n\n{user_msg}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

        raw = self.llm.chat_text(messages)
        return self._parse_response(raw, plan)

    def _parse_response(self, raw: str, plan: ActionPlan) -> GeneratedAction | None:
        # Try to find JSON array
        start = raw.rfind("[")
        end = raw.rfind("]") + 1
        if start < 0 or end <= start:
            logger.warning("No JSON array found in LLM response for %s", plan.action_id)
            return None

        try:
            data = json.loads(raw[start:end])
            if not isinstance(data, list) or len(data) == 0:
                return None
            action_data = data[0]
            ra = ResponseAction(**action_data)
            return GeneratedAction(
                plan=plan,
                content=ra.content,
                llm_raw=raw,
                mentions=[ra.mention_user_id] if ra.mention_user_id else [],
                reply_to=ra.reply_to_message_id,
            )
        except Exception as e:
            logger.warning("Failed to parse LLM response for %s: %s", plan.action_id, e)
            return None
