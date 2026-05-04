import json
import queue
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from conf.schema import BotConfig
from core.activity_curve import ActivityCurve
from core.degraded_policy import DegradedReplyPolicy
from core.decision import DecisionEngine
from core.emergency_brake import EmergencyBrake
from core.orchestrator import Orchestrator
from core.passive_judge import PassiveReplyJudge
from core.active_gate import ActiveSpeakGate
from core.schemas import (
    ActionPlan, ActionType, BrakeDecision, DecisionResult,
    GeneratedAction, Priority, RuntimeMode, StateEvent, StateEventType, TickType,
)
from core.state import BotState, StateEventQueue
from generation.content_gen import ContentGenerator
from generation.formatter import ResponseFormatter
from infra.action_log import ActionLog
from infra.bot_adapter import BotAdapter, SendResult, SendStatus
from infra.llm_client import LLMClient
from infra.message_ingestor import MessageIngestor
from infra.raw_message_log import RawMessageLog
from memory.concentrator import ConcentrateJob
from memory.manager import MemoryManager
from memory.schemas import Message
from ui.sender import DelaySendScheduler


def _make_config() -> BotConfig:
    cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
    cfg.send.passive_delay_min = 0.01
    cfg.send.passive_delay_max = 0.05
    cfg.send.active_delay_min = 0.01
    cfg.send.active_delay_max = 0.05
    cfg.send.min_interval_same_chat = 0.1
    cfg.memory.pending_threshold = 3
    return cfg


def _make_plan(action_id: str = "a-001", priority: Priority = Priority.P0) -> ActionPlan:
    return ActionPlan(
        action_id=action_id, action_type=ActionType.PASSIVE_REPLY,
        priority=priority, chat_id="100", chat_type="group",
        trigger_message="hello", trigger_type="passive_tick", reason="test",
    )


def _make_action(action_id: str = "a-001", content: str = "reply") -> GeneratedAction:
    return GeneratedAction(plan=_make_plan(action_id), content=content)


def _build_orchestrator(tmp_db_path: str, llm_mock: MagicMock | None = None):
    cfg = _make_config()
    state = BotState(cfg, ActivityCurve(cfg.activity))
    state.transition(RuntimeMode.STARTING)
    state.transition(RuntimeMode.RUNNING)
    state_events = StateEventQueue()

    memory = MemoryManager()
    raw_log = RawMessageLog(tmp_db_path + ".raw")
    action_log = ActionLog(tmp_db_path + ".action")
    long_term_mock = MagicMock()
    relationship_mock = MagicMock()
    entity_mock = MagicMock()

    llm = llm_mock or MagicMock(spec=LLMClient)
    llm.chat_text.return_value = '[{"content": "hi", "mention_user_id": null, "reply_to_message_id": null}]'

    incoming_queue: queue.Queue = queue.Queue()
    ingestor = MessageIngestor(incoming_queue, memory, raw_log)

    passive_judge = PassiveReplyJudge(cfg)
    active_gate = ActiveSpeakGate(cfg, state)
    engine = DecisionEngine(passive_judge, active_gate, memory, llm)

    formatter = MagicMock(spec=ResponseFormatter)
    formatter.format_system_prompt.return_value = "system"
    formatter.format_response_prompt.return_value = "respond in json"
    content_gen = ContentGenerator(llm, formatter)
    degraded_policy = DegradedReplyPolicy(cfg)

    brake = EmergencyBrake(cfg)
    adapter = MagicMock(spec=BotAdapter)
    adapter.send_group_msg.side_effect = lambda gid, content, **kw: SendResult(
        action_id=kw.get("action_id", ""), status=SendStatus.SENT, latency_ms=10,
    )
    sender = DelaySendScheduler(adapter, action_log, brake, state_events, cfg)

    concentrator = ConcentrateJob(llm, long_term_mock, cfg)

    orch = Orchestrator(
        state=state, engine=engine, content_gen=content_gen, brake=brake,
        sender=sender, action_log=action_log, memory=memory, llm=llm,
        degraded_policy=degraded_policy, config=cfg, state_events=state_events,
        ingestor=ingestor, concentrator=concentrator,
    )
    return orch, state, memory, adapter, action_log, incoming_queue, sender


class TestOrchestratorPassive:
    def test_passive_no_messages(self, tmp_db_path):
        orch, state, _, adapter, _, _, _ = _build_orchestrator(tmp_db_path)
        orch.run_passive_tick()
        assert adapter.send_group_msg.call_count == 0

    def test_passive_with_at_message(self, tmp_db_path):
        orch, state, memory, adapter, _, _, sender = _build_orchestrator(tmp_db_path)
        sender.start()
        # Add an @bot message
        msg = Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="Alice", group_nickname="Alice",
            content="@123 你好", timestamp=datetime.now(),
        )
        memory.add_message(msg)

        orch.run_passive_tick()
        import time
        time.sleep(0.3)

        assert adapter.send_group_msg.call_count == 1
        sender.stop()

    def test_passive_degraded_uses_templates(self, tmp_db_path):
        orch, state, memory, adapter, action_log, _, sender = _build_orchestrator(tmp_db_path)
        orch.degraded_policy.silence_probability = 0.0
        sender.start()
        # Force degraded mode
        for _ in range(5):
            state.apply(StateEvent(event_type=StateEventType.LLM_FAILED))
        assert state.mode == RuntimeMode.DEGRADED

        msg = Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="Alice", group_nickname="Alice",
            content="@123 你好", timestamp=datetime.now(),
        )
        memory.add_message(msg)

        orch.run_passive_tick()
        import time
        time.sleep(0.3)

        # Should still send (via template)
        assert adapter.send_group_msg.call_count == 1
        sender.stop()

    def test_passive_llm_failure_emits_event(self, tmp_db_path):
        from infra.llm_client import LLMError
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.side_effect = LLMError("LLM down")
        orch, state, memory, _, _, _, _ = _build_orchestrator(tmp_db_path, llm_mock=llm)

        msg = Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="Alice", group_nickname="Alice",
            content="@123 你好", timestamp=datetime.now(),
        )
        memory.add_message(msg)

        orch.run_passive_tick()
        events = orch.state_events.drain()
        assert any(e.event_type == StateEventType.LLM_FAILED for e in events)


class TestOrchestratorActive:
    def test_active_only_runs_in_running(self, tmp_db_path):
        orch, state, _, adapter, _, _, _ = _build_orchestrator(tmp_db_path)
        state.mode = RuntimeMode.DEGRADED
        orch.run_active_tick()
        assert adapter.send_group_msg.call_count == 0

    def test_active_no_messages_no_action(self, tmp_db_path):
        orch, state, _, adapter, _, _, _ = _build_orchestrator(tmp_db_path)
        orch.run_active_tick()
        assert adapter.send_group_msg.call_count == 0


class TestOrchestratorConcentrate:
    def test_concentrate_only_in_running(self, tmp_db_path):
        orch, state, memory, _, _, _, _ = _build_orchestrator(tmp_db_path)
        state.mode = RuntimeMode.PAUSED
        orch.run_concentrate_tick()
        # Should not crash, should not call LLM

    def test_concentrate_skips_below_threshold(self, tmp_db_path):
        orch, state, memory, _, _, _, _ = _build_orchestrator(tmp_db_path)
        # Add a few messages but below threshold
        for i in range(2):
            memory.add_message(Message(
                message_id=f"m{i}", chat_type="group", chat_id="100",
                user_id="200", user_nickname="Alice", group_nickname="Alice",
                content=f"msg {i}", timestamp=datetime.now(),
            ))
        chat = memory.get_chat("100")
        chat.consume_unread()

        orch.run_concentrate_tick()
        # LLM should not be called for concentrate
        orch.llm.chat_text.assert_not_called()


class TestOrchestratorBrakeIntegration:
    def test_brake_cancel_removes_action(self, tmp_db_path):
        orch, state, memory, adapter, action_log, _, sender = _build_orchestrator(tmp_db_path)
        sender.start()
        # Patch final_check to return CANCEL
        orch.brake.final_check = MagicMock(return_value=BrakeDecision.CANCEL)

        msg = Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="Alice", group_nickname="Alice",
            content="@123 你好", timestamp=datetime.now(),
        )
        memory.add_message(msg)

        orch.run_passive_tick()
        import time
        time.sleep(0.1)

        assert adapter.send_group_msg.call_count == 0
        sender.stop()
