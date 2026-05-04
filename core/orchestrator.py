from __future__ import annotations

import logging
from datetime import datetime

from conf.schema import BotConfig
from core.degraded_policy import DegradedReplyPolicy
from core.decision import DecisionEngine
from core.emergency_brake import EmergencyBrake
from core.schemas import (
    BrakeDecision,
    GeneratedAction,
    RuntimeMode,
    StateEvent,
    StateEventType,
    TickType,
)
from core.state import BotState, StateEventQueue
from generation.content_gen import ContentGenerator
from infra.action_log import ActionLog
from infra.llm_client import LLMClient
from infra.message_ingestor import MessageIngestor
from memory.concentrator import ConcentrateJob
from memory.manager import MemoryManager
from ui.sender import DelaySendScheduler

logger = logging.getLogger(__name__)

_PASSIVE_ONLY_MODES = {RuntimeMode.PAUSED, RuntimeMode.ERROR, RuntimeMode.STOPPING, RuntimeMode.STOPPED, RuntimeMode.STARTING}


class Orchestrator:
    def __init__(
        self,
        state: BotState,
        engine: DecisionEngine,
        content_gen: ContentGenerator,
        brake: EmergencyBrake,
        sender: DelaySendScheduler,
        action_log: ActionLog,
        memory: MemoryManager,
        llm: LLMClient,
        degraded_policy: DegradedReplyPolicy,
        config: BotConfig,
        state_events: StateEventQueue,
        ingestor: MessageIngestor,
        concentrator: ConcentrateJob,
    ):
        self.state = state
        self.engine = engine
        self.content_gen = content_gen
        self.brake = brake
        self.sender = sender
        self.action_log = action_log
        self.memory = memory
        self.llm = llm
        self.degraded_policy = degraded_policy
        self.config = config
        self.state_events = state_events
        self.ingestor = ingestor
        self.concentrator = concentrator

    def _drain_ingest(self) -> int:
        return self.ingestor.drain(max_items=50)

    def _drain_state_events(self) -> None:
        for event in self.state_events.drain():
            self.state.apply(event)

    def _emit_event(self, event_type: StateEventType, payload: dict | None = None) -> None:
        self.state_events.put(StateEvent(
            event_type=event_type,
            payload=payload or {},
            timestamp=datetime.now(),
        ))

    def run_passive_tick(self) -> None:
        self._drain_ingest()
        self._drain_state_events()
        self.state.tick(datetime.now())

        if self.state.mode in _PASSIVE_ONLY_MODES:
            return

        # DEGRADED health check every 10 cycles
        if self.state.mode == RuntimeMode.DEGRADED:
            if self.state.cycle_count % self.config.llm.health_check_interval == 0:
                try:
                    if self.llm.health_check():
                        self._emit_event(StateEventType.LLM_RECOVERED)
                except Exception:
                    pass
            # In DEGRADED mode, still allow passive with templates
            decision = self.engine.decide(TickType.PASSIVE)
            if not decision.plans:
                return
            self.action_log.record_planned(decision.plans)
            generated = self.degraded_policy.generate(decision.plans)
            self._record_and_schedule(generated)
            return

        decision = self.engine.decide(TickType.PASSIVE)
        if not decision.plans:
            return

        self.action_log.record_planned(decision.plans)

        try:
            generated = self.content_gen.generate(decision.plans)
        except Exception as e:
            logger.error("Content generation failed in passive tick: %s", e)
            self._emit_event(StateEventType.LLM_FAILED, {"tick_type": "passive", "error": str(e)})
            self.action_log.record_batch(decision.plans, "cancelled", "llm_failure")
            return

        self._record_and_schedule(generated)

    def run_active_tick(self) -> None:
        if self.state.mode != RuntimeMode.RUNNING:
            return

        self._drain_ingest()
        self._drain_state_events()
        self.state.tick(datetime.now())

        try:
            decision = self.engine.decide(TickType.ACTIVE)
        except Exception as e:
            logger.error("Active decision failed: %s", e)
            self._emit_event(StateEventType.LLM_FAILED, {"tick_type": "active", "error": str(e)})
            return

        if not decision.plans:
            return

        self.action_log.record_planned(decision.plans)

        try:
            generated = self.content_gen.generate(decision.plans)
        except Exception as e:
            logger.error("Content generation failed in active tick: %s", e)
            self._emit_event(StateEventType.LLM_FAILED, {"tick_type": "active", "error": str(e)})
            self.action_log.record_batch(decision.plans, "cancelled", "llm_failure")
            return

        self._record_and_schedule(generated)

    def run_concentrate_tick(self) -> None:
        if self.state.mode != RuntimeMode.RUNNING:
            return

        for chat in self.memory.get_all_chats():
            if chat.should_concentrate(self.config.memory.pending_threshold):
                success = self.concentrator.run(chat)
                if not success:
                    self._emit_event(StateEventType.LLM_FAILED, {
                        "tick_type": "concentrate",
                        "chat_id": chat.chat_id,
                    })

    def _record_and_schedule(self, generated: list[GeneratedAction]) -> None:
        if not generated:
            return

        self.action_log.record_generated(generated)

        to_send: list[GeneratedAction] = []
        for g in generated:
            decision = self.brake.final_check(g)
            if decision == BrakeDecision.ALLOW:
                to_send.append(g)
            elif decision == BrakeDecision.CANCEL:
                self.action_log.record(g.plan, "cancelled", "final_check")
            elif decision == BrakeDecision.DELAY:
                delay = self.config.send.min_interval_same_chat
                self.sender.schedule(g, delay=delay)
                to_send.append(g)  # still record as scheduled
            elif decision == BrakeDecision.MERGE:
                # Re-generate and add result
                try:
                    regen = self.content_gen.generate([g.plan])
                    if regen:
                        to_send.extend(regen)
                except Exception:
                    self.action_log.record(g.plan, "cancelled", "merge_regen_failed")

        if to_send:
            self.sender.schedule_many(to_send)
            self.action_log.record_scheduled(to_send)
