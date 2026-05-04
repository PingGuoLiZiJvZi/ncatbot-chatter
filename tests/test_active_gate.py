from datetime import datetime
from unittest.mock import MagicMock
import pytest
from conf.schema import BotConfig
from core.active_gate import ActiveSpeakGate
from core.schemas import RuntimeMode
from core.state import BotState
from core.activity_curve import ActivityCurve
from infra.llm_client import LLMError
from infra.llm_schemas import DecisionOutput
from memory.schemas import Message
from memory.short_term import ShortTermMemory


def _make_config() -> BotConfig:
    return BotConfig(bot_uin="12345", root_uin="99999", api_key="sk-test")


def _make_state(config: BotConfig | None = None) -> BotState:
    cfg = config or _make_config()
    return BotState(cfg, ActivityCurve(cfg.activity))


class TestHardThresholds:
    def test_time_suppression_deep_night(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.activity_weight = 0.0
        gate = ActiveSpeakGate(cfg, state)
        assert gate._check_time_suppression() is True

    def test_time_suppression_daytime(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.activity_weight = 0.8
        gate = ActiveSpeakGate(cfg, state)
        assert gate._check_time_suppression() is False

    def test_energy_suppression_low_energy(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.energy = 0.1
        gate = ActiveSpeakGate(cfg, state)
        assert gate._check_energy_suppression() is True

    def test_energy_suppression_low_social_battery(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.energy = 0.5
        state.social_battery = 0.1
        gate = ActiveSpeakGate(cfg, state)
        assert gate._check_energy_suppression() is True

    def test_energy_suppression_ok(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.energy = 0.5
        state.social_battery = 0.5
        gate = ActiveSpeakGate(cfg, state)
        assert gate._check_energy_suppression() is False

    def test_check_hard_thresholds_all_pass(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.activity_weight = 0.8
        state.energy = 0.5
        state.social_battery = 0.5
        gate = ActiveSpeakGate(cfg, state)
        assert gate.check_hard_thresholds() is True

    def test_check_hard_thresholds_time_fail(self):
        cfg = _make_config()
        state = _make_state(cfg)
        state.activity_weight = 0.0
        gate = ActiveSpeakGate(cfg, state)
        assert gate.check_hard_thresholds() is False


class TestLLMEvaluation:
    def test_evaluate_returns_none_when_no_chats(self):
        cfg = _make_config()
        state = _make_state(cfg)
        gate = ActiveSpeakGate(cfg, state)
        llm = MagicMock()
        memory = MagicMock()
        result = gate.evaluate_with_llm([], llm, memory)
        assert result is None

    def test_evaluate_success(self):
        cfg = _make_config()
        state = _make_state(cfg)
        gate = ActiveSpeakGate(cfg, state)
        llm = MagicMock()
        llm.chat_text.return_value = '{"should_speak": true, "chat_id": "100", "intent": "say hi", "reason": "greeting"}'
        memory = MagicMock()

        chat = ShortTermMemory("100")
        chat.add_incoming(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="test", group_nickname="test",
            content="hello", timestamp=datetime.now(),
        ))
        chat.consume_unread()

        result = gate.evaluate_with_llm([chat], llm, memory)
        assert result is not None
        assert result.should_speak is True
        assert result.chat_id == "100"

    def test_evaluate_llm_failure_raises(self):
        cfg = _make_config()
        state = _make_state(cfg)
        gate = ActiveSpeakGate(cfg, state)
        llm = MagicMock()
        llm.chat_text.side_effect = LLMError("timeout")
        memory = MagicMock()

        chat = ShortTermMemory("100")
        chat.add_incoming(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="test", group_nickname="test",
            content="hello", timestamp=datetime.now(),
        ))
        chat.consume_unread()

        with pytest.raises(LLMError):
            gate.evaluate_with_llm([chat], llm, memory)

    def test_evaluate_invalid_json_returns_none(self):
        cfg = _make_config()
        state = _make_state(cfg)
        gate = ActiveSpeakGate(cfg, state)
        llm = MagicMock()
        llm.chat_text.return_value = "I don't want to speak"
        memory = MagicMock()

        chat = ShortTermMemory("100")
        chat.add_incoming(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="test", group_nickname="test",
            content="hello", timestamp=datetime.now(),
        ))
        chat.consume_unread()

        result = gate.evaluate_with_llm([chat], llm, memory)
        assert result is None
