from datetime import datetime, timedelta
import pytest
from conf.schema import BotConfig
from core.emergency_brake import EmergencyBrake
from core.schemas import ActionPlan, ActionType, BrakeDecision, GeneratedAction, Priority, ChatState
from core.state import BotState
from core.activity_curve import ActivityCurve
from memory.manager import MemoryManager


def _make_config() -> BotConfig:
    return BotConfig(bot_uin="12345", root_uin="99999", api_key="sk-test")


def _make_plan(action_id: str = "a-001", priority: Priority = Priority.P0) -> ActionPlan:
    return ActionPlan(
        action_id=action_id, action_type=ActionType.PASSIVE_REPLY,
        priority=priority, chat_id="100", chat_type="group",
        trigger_message="hello", trigger_type="passive_tick", reason="test",
    )


def _make_action(action_id: str = "a-001", content: str = "hello!", priority: Priority = Priority.P0) -> GeneratedAction:
    plan = _make_plan(action_id, priority)
    return GeneratedAction(plan=plan, content=content)


def _make_state() -> BotState:
    cfg = _make_config()
    return BotState(cfg, ActivityCurve(cfg.activity))


class TestPrecheck:
    def test_p0_allows_even_with_min_interval(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.last_bot_send_at = datetime.now() - timedelta(seconds=10)
        plan = _make_plan(priority=Priority.P0)
        assert brake.precheck(plan, state) == BrakeDecision.ALLOW

    def test_p1_delays_with_min_interval(self):
        cfg = _make_config()
        cfg.send.min_interval_same_chat = 120
        brake = EmergencyBrake(cfg)
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.last_bot_send_at = datetime.now() - timedelta(seconds=10)
        plan = _make_plan(priority=Priority.P1)
        assert brake.precheck(plan, state) == BrakeDecision.DELAY

    def test_p2_cancels_with_min_interval(self):
        cfg = _make_config()
        cfg.send.min_interval_same_chat = 120
        brake = EmergencyBrake(cfg)
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.last_bot_send_at = datetime.now() - timedelta(seconds=10)
        plan = _make_plan(priority=Priority.P2)
        assert brake.precheck(plan, state) == BrakeDecision.CANCEL

    def test_no_previous_send(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        plan = _make_plan()
        assert brake.precheck(plan, state) == BrakeDecision.ALLOW


class TestFinalCheck:
    def test_empty_content_cancel(self):
        brake = EmergencyBrake(_make_config())
        action = _make_action(content="")
        assert brake.final_check(action) == BrakeDecision.CANCEL

    def test_long_content_cancel(self):
        brake = EmergencyBrake(_make_config())
        action = _make_action(content="x" * 501)
        assert brake.final_check(action) == BrakeDecision.CANCEL

    def test_ai_phrase_cancel(self):
        brake = EmergencyBrake(_make_config())
        action = _make_action(content="作为一个AI，我认为...")
        assert brake.final_check(action) == BrakeDecision.CANCEL

    def test_normal_content_allow(self):
        brake = EmergencyBrake(_make_config())
        action = _make_action(content="hello!")
        assert brake.final_check(action) == BrakeDecision.ALLOW


class TestPreSendCheck:
    def test_bot_msg_count_high_cancel(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.recent_bot_msg_count = 3
        memory = MemoryManager()
        action = _make_action()
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.CANCEL

    def test_empty_content_cancel(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        memory = MemoryManager()
        action = _make_action(content="")
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.CANCEL

    def test_old_action_cancel(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        memory = MemoryManager()
        plan = _make_plan()
        plan.created_at = datetime.now() - timedelta(seconds=400)
        action = GeneratedAction(plan=plan, content="hello!")
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.CANCEL

    def test_normal_pass(self):
        brake = EmergencyBrake(_make_config())
        state = _make_state()
        memory = MemoryManager()
        action = _make_action()
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.ALLOW

    def test_p2_with_min_interval_cancel(self):
        cfg = _make_config()
        cfg.send.min_interval_same_chat = 120
        brake = EmergencyBrake(cfg)
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.last_bot_send_at = datetime.now() - timedelta(seconds=10)
        memory = MemoryManager()
        action = _make_action(priority=Priority.P2)
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.CANCEL

    def test_p0_with_min_interval_delay(self):
        cfg = _make_config()
        cfg.send.min_interval_same_chat = 120
        brake = EmergencyBrake(cfg)
        state = _make_state()
        cs = state.get_chat_state("100")
        cs.last_bot_send_at = datetime.now() - timedelta(seconds=10)
        memory = MemoryManager()
        action = _make_action(priority=Priority.P0)
        assert brake.pre_send_check(action, state, memory) == BrakeDecision.DELAY
