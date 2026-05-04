from __future__ import annotations

import logging
from uuid import uuid4

from core.schemas import (
    ActionPlan,
    ActionType,
    DecisionResult,
    Priority,
    TickType,
)
from core.passive_judge import PassiveReplyJudge
from core.active_gate import ActiveSpeakGate
from memory.manager import MemoryManager
from infra.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(
        self,
        passive_judge: PassiveReplyJudge,
        active_gate: ActiveSpeakGate,
        memory: MemoryManager,
        llm: LLMClient,
    ):
        self.passive_judge = passive_judge
        self.active_gate = active_gate
        self.memory = memory
        self.llm = llm

    def decide(self, tick_type: TickType) -> DecisionResult:
        if tick_type == TickType.PASSIVE:
            return self._decide_passive()
        elif tick_type == TickType.ACTIVE:
            return self._decide_active()
        return DecisionResult(plans=[], trigger_type=tick_type.value)

    def _decide_passive(self) -> DecisionResult:
        chats = self.memory.get_active_chats()
        plans = self.passive_judge.evaluate(chats)
        return DecisionResult(plans=plans, trigger_type="passive_tick")

    def _decide_active(self) -> DecisionResult:
        if not self.active_gate.check_hard_thresholds():
            return DecisionResult(plans=[], trigger_type="active_tick")

        chats = [c for c in self.memory.get_all_chats() if c.get_read()]
        decision_output = self.active_gate.evaluate_with_llm(chats, self.llm, self.memory)
        if decision_output and decision_output.should_speak and decision_output.chat_id:
            plan = ActionPlan(
                action_id=str(uuid4()),
                action_type=ActionType.ACTIVE_SPEAK,
                priority=Priority.P2,
                chat_id=decision_output.chat_id,
                chat_type="group",
                trigger_message=None,
                trigger_type="active_intent",
                reason=decision_output.reason or decision_output.intent or "active_speak",
            )
            return DecisionResult(plans=[plan], trigger_type="active_tick")
        return DecisionResult(plans=[], trigger_type="active_tick")
