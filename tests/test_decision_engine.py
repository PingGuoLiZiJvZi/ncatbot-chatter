from datetime import datetime
from unittest.mock import MagicMock
import pytest
from conf.schema import BotConfig
from core.decision import DecisionEngine
from core.passive_judge import PassiveReplyJudge
from core.active_gate import ActiveSpeakGate
from core.schemas import TickType, Priority, ActionType
from core.state import BotState
from core.activity_curve import ActivityCurve
from infra.llm_client import LLMClient
from infra.llm_schemas import DecisionOutput
from memory.manager import MemoryManager
from memory.schemas import Message


def _make_config() -> BotConfig:
    return BotConfig(bot_uin="12345", root_uin="99999", api_key="sk-test")


def _make_engine(config: BotConfig | None = None, llm: LLMClient | None = None):
    cfg = config or _make_config()
    state = BotState(cfg, ActivityCurve(cfg.activity))
    state.mode = "RUNNING"
    memory = MemoryManager()
    passive = PassiveReplyJudge(cfg)
    active = ActiveSpeakGate(cfg, state)
    mock_llm = llm or MagicMock()
    return DecisionEngine(passive, active, memory, mock_llm), memory, state


class TestDecisionEngine:
    def test_passive_with_at_message(self):
        engine, memory, _ = _make_engine()
        memory.add_message(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="test", group_nickname="test",
            content="@12345 hello", timestamp=datetime.now(),
        ))
        result = engine.decide(TickType.PASSIVE)
        assert len(result.plans) == 1
        assert result.plans[0].priority == Priority.P0

    def test_passive_no_messages(self):
        engine, memory, _ = _make_engine()
        result = engine.decide(TickType.PASSIVE)
        assert len(result.plans) == 0

    def test_active_hard_threshold_fail(self):
        engine, memory, state = _make_engine()
        state.activity_weight = 0.0  # deep night
        result = engine.decide(TickType.ACTIVE)
        assert len(result.plans) == 0

    def test_active_llm_says_speak(self):
        mock_llm = MagicMock()
        mock_llm.chat_text.return_value = '{"should_speak": true, "chat_id": "100", "intent": "say hi", "reason": "greeting"}'
        engine, memory, state = _make_engine(llm=mock_llm)
        state.activity_weight = 0.8
        state.energy = 0.5
        state.social_battery = 0.5

        # Add a chat with read messages
        memory.add_message(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="test", group_nickname="test",
            content="hello everyone", timestamp=datetime.now(),
        ))
        chat = memory.get_chat("100")
        chat.consume_unread()

        result = engine.decide(TickType.ACTIVE)
        assert len(result.plans) == 1
        assert result.plans[0].action_type == ActionType.ACTIVE_SPEAK

    def test_active_llm_says_silent(self):
        mock_llm = MagicMock()
        mock_llm.chat_text.return_value = '{"should_speak": false}'
        engine, memory, state = _make_engine(llm=mock_llm)
        state.activity_weight = 0.8
        state.energy = 0.5
        state.social_battery = 0.5

        result = engine.decide(TickType.ACTIVE)
        assert len(result.plans) == 0
