from datetime import datetime
from uuid import UUID

from core.schemas import (
    Priority, ActionType, TickType, RuntimeMode, BrakeDecision,
    StateEventType, ActionPlan, GeneratedAction, DecisionResult,
    StateEvent, ChatState,
)
from memory.schemas import MemoryType, Message, SelfMessage, MemoryEntry, MemoryContext
from infra.llm_schemas import DecisionOutput, ResponseAction, ResponseOutput, ConcentrateItem, ConcentrateOutput


class TestEnums:
    def test_priority_values(self):
        assert Priority.P0.value == "P0"
        assert Priority.P1.value == "P1"
        assert Priority.P2.value == "P2"

    def test_action_type_values(self):
        assert ActionType.PASSIVE_REPLY.value == "PASSIVE_REPLY"
        assert ActionType.ACTIVE_SPEAK.value == "ACTIVE_SPEAK"

    def test_tick_type_values(self):
        assert TickType.PASSIVE.value == "PASSIVE"
        assert TickType.ACTIVE.value == "ACTIVE"
        assert TickType.CONCENTRATE.value == "CONCENTRATE"

    def test_runtime_mode_values(self):
        assert len(RuntimeMode) == 8
        for mode in RuntimeMode:
            assert isinstance(mode.value, str)

    def test_brake_decision_values(self):
        assert BrakeDecision.ALLOW.value == "allow"
        assert BrakeDecision.CANCEL.value == "cancel"
        assert BrakeDecision.DELAY.value == "delay"
        assert BrakeDecision.MERGE.value == "merge"

    def test_state_event_type_values(self):
        assert StateEventType.MESSAGE_SENT.value == "MESSAGE_SENT"
        assert StateEventType.LLM_FAILED.value == "LLM_FAILED"

    def test_memory_type_values(self):
        assert MemoryType.EVENT.value == "event"
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.IMPRESSION.value == "impression"
        assert MemoryType.PLAN.value == "plan"


class TestCoreSchemas:
    def test_action_plan(self):
        plan = ActionPlan(
            action_id="test-001",
            action_type=ActionType.PASSIVE_REPLY,
            priority=Priority.P0,
            chat_id="123456",
            chat_type="group",
            trigger_message="hello",
            trigger_type="passive_tick",
            reason="mentioned",
        )
        assert plan.action_id == "test-001"
        assert plan.priority == Priority.P0
        assert isinstance(plan.created_at, datetime)

    def test_generated_action(self):
        plan = ActionPlan(
            action_id="g-001",
            action_type=ActionType.ACTIVE_SPEAK,
            priority=Priority.P2,
            chat_id="789",
            chat_type="group",
            trigger_message=None,
            trigger_type="active_intent",
            reason="bored",
        )
        action = GeneratedAction(plan=plan, content="hello!")
        assert action.content == "hello!"
        assert action.mentions == []
        assert action.reply_to is None

    def test_decision_result(self):
        result = DecisionResult(plans=[], trigger_type="passive_tick")
        assert result.plans == []

    def test_state_event(self):
        event = StateEvent(
            event_type=StateEventType.LLM_FAILED,
            payload={"error": "timeout"},
        )
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.timestamp, datetime)

    def test_chat_state(self):
        cs = ChatState(chat_id="123")
        assert cs.last_bot_send_at is None
        assert cs.recent_bot_msg_count == 0


class TestMemorySchemas:
    def test_message(self):
        msg = Message(
            message_id="msg-001",
            chat_type="group",
            chat_id="123",
            user_id="456",
            user_nickname="test",
            group_nickname="test_group",
            content="hello",
            timestamp=datetime.now(),
        )
        assert msg.message_id == "msg-001"

    def test_self_message(self):
        sm = SelfMessage(
            chat_type="group",
            chat_id="123",
            content="reply",
            timestamp=datetime.now(),
            action_id="a-001",
        )
        assert sm.action_id == "a-001"

    def test_memory_entry_defaults(self):
        entry = MemoryEntry()
        assert entry.memory_type == MemoryType.EVENT
        assert entry.importance == 5
        assert entry.is_active == 1

    def test_memory_context(self):
        ctx = MemoryContext(query="test", chat_id="123")
        assert ctx.entries == []


class TestLLMSchemas:
    def test_decision_output(self):
        do = DecisionOutput(should_speak=True, chat_id="123", intent="say hi", reason="greeting")
        assert do.should_speak is True

    def test_decision_output_minimal(self):
        do = DecisionOutput(should_speak=False)
        assert do.chat_id is None

    def test_response_action(self):
        ra = ResponseAction(content="hello")
        assert ra.mention_user_id is None

    def test_response_output(self):
        ro = ResponseOutput(actions=[ResponseAction(content="hi")])
        assert len(ro.actions) == 1

    def test_concentrate_item(self):
        ci = ConcentrateItem(
            memory_type=MemoryType.EVENT,
            summary="test event",
            importance=7,
            confidence=0.9,
            keywords=["test"],
            source_message_ids=["m1"],
        )
        assert ci.importance == 7

    def test_concentrate_output(self):
        co = ConcentrateOutput(entries=[])
        assert co.entries == []
