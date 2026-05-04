from __future__ import annotations

import logging
import random

from conf.schema import BotConfig
from core.schemas import ActionPlan, GeneratedAction

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES = [
    "嗯",
    "哦",
    "好的",
    "知道了",
    "哈哈",
    "...",
    "嗯嗯",
]


class DegradedReplyPolicy:
    def __init__(self, config: BotConfig, templates: list[str] | None = None):
        self.config = config
        self.templates = templates or _DEFAULT_TEMPLATES
        self.silence_probability = 0.3

    def generate(self, plans: list[ActionPlan]) -> list[GeneratedAction]:
        results = []
        for plan in plans:
            if random.random() < self.silence_probability:
                logger.debug("Degraded: skipping reply for %s (silence)", plan.action_id)
                continue
            template = random.choice(self.templates)
            results.append(GeneratedAction(
                plan=plan,
                content=template,
                llm_raw="[degraded_template]",
            ))
        return results
