from __future__ import annotations

import logging
import re
from datetime import datetime

from conf.schema import BotConfig
from core.schemas import ActionPlan, BrakeDecision, GeneratedAction, Priority
from core.state import BotState
from memory.manager import MemoryManager

logger = logging.getLogger(__name__)

_AI_PATTERNS = [
    r"作为一个AI",
    r"我是(?:一个)?(?:AI|人工智能|助手|语言模型)",
    r"作为(?:一个)?(?:AI|语言模型)",
    r"我没有(?:个人|真实)(?:观点|想法|感受)",
    r"我无法(?:真正|实际)",
]
_AI_RE = re.compile("|".join(_AI_PATTERNS))


class EmergencyBrake:
    def __init__(self, config: BotConfig):
        self.config = config

    def precheck(self, plan: ActionPlan, state: BotState) -> BrakeDecision:
        cs = state.get_chat_state(plan.chat_id)
        now = datetime.now()
        if cs.last_bot_send_at:
            elapsed = (now - cs.last_bot_send_at).total_seconds()
            if elapsed < self.config.send.min_interval_same_chat:
                if plan.priority == Priority.P0:
                    return BrakeDecision.ALLOW
                elif plan.priority == Priority.P1:
                    return BrakeDecision.DELAY
                else:
                    return BrakeDecision.CANCEL
        return BrakeDecision.ALLOW

    def final_check(self, action: GeneratedAction) -> BrakeDecision:
        content = action.content.strip()
        if not content:
            logger.warning("Brake: empty content for action %s", action.plan.action_id)
            return BrakeDecision.CANCEL
        if len(content) > 500:
            logger.warning("Brake: content too long (%d chars) for action %s", len(content), action.plan.action_id)
            return BrakeDecision.CANCEL
        if _AI_RE.search(content):
            logger.warning("Brake: AI-sounding phrase detected in action %s", action.plan.action_id)
            return BrakeDecision.CANCEL
        return BrakeDecision.ALLOW

    def pre_send_check(
        self,
        action: GeneratedAction,
        state: BotState,
        memory: MemoryManager,
    ) -> BrakeDecision:
        # Rule 1: bot already sent 3+ of last 5 messages
        cs = state.get_chat_state(action.plan.chat_id)
        if cs.recent_bot_msg_count >= 3:
            logger.warning("Pre-send: bot msg count >= 3 in chat %s", action.plan.chat_id)
            return BrakeDecision.CANCEL

        # Rule 2: content validity (same as final_check)
        content = action.content.strip()
        if not content or len(content) > 500 or _AI_RE.search(content):
            return BrakeDecision.CANCEL

        # Rule 3: P2 active + min_interval
        if action.plan.priority == Priority.P2 and cs.last_bot_send_at:
            elapsed = (datetime.now() - cs.last_bot_send_at).total_seconds()
            if elapsed < self.config.send.min_interval_same_chat:
                return BrakeDecision.CANCEL

        # Rule 4: P0/P1 + min_interval → DELAY
        if action.plan.priority in (Priority.P0, Priority.P1) and cs.last_bot_send_at:
            elapsed = (datetime.now() - cs.last_bot_send_at).total_seconds()
            if elapsed < self.config.send.min_interval_same_chat:
                return BrakeDecision.DELAY

        # Rule 5: trigger_message too old (>5 min)
        if action.plan.created_at:
            age = (datetime.now() - action.plan.created_at).total_seconds()
            if age > 300:
                logger.warning("Pre-send: action too old (%.0fs) for %s", age, action.plan.action_id)
                return BrakeDecision.CANCEL

        return BrakeDecision.ALLOW
