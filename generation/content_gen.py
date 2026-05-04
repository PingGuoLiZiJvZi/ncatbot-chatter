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
        # Try multiple strategies to extract a JSON array
        data = self._extract_json_array(raw)
        if data is None:
            logger.warning("No valid JSON array found in LLM response for %s", plan.action_id)
            return None

        try:
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

    @staticmethod
    def _extract_json_array(raw: str) -> list | None:
        """Try multiple strategies to extract a JSON array from LLM output."""
        import re

        # Strategy 1: direct parse of the whole string
        try:
            result = json.loads(raw.strip())
            if isinstance(result, list) and len(result) > 0:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: strip markdown code fences
        fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if fenced:
            try:
                result = json.loads(fenced.group(1))
                if isinstance(result, list) and len(result) > 0:
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: find outermost [ ... ] and parse
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            candidate = raw[start:end + 1]
            # 3a: direct parse
            try:
                result = json.loads(candidate)
                if isinstance(result, list) and len(result) > 0:
                    return result
            except (json.JSONDecodeError, ValueError):
                pass
            # 3b: strip trailing commas before ] or }
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                result = json.loads(fixed)
                if isinstance(result, list) and len(result) > 0:
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 4: regex to find individual { ... } objects and reassemble
        objects = re.findall(r"\{[^{}]*\}", raw)
        if objects:
            parsed = []
            for obj_str in objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict) and "content" in obj:
                        parsed.append(obj)
                except (json.JSONDecodeError, ValueError):
                    continue
            if parsed:
                return parsed

        return None
