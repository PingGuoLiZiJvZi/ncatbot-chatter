from unittest.mock import MagicMock
import pytest
from core.schemas import ActionPlan, ActionType, Priority
from generation.content_gen import ContentGenerator
from generation.formatter import ResponseFormatter
from infra.llm_client import LLMClient, LLMError


def _make_plan(action_id: str = "a-001") -> ActionPlan:
    return ActionPlan(
        action_id=action_id, action_type=ActionType.PASSIVE_REPLY,
        priority=Priority.P0, chat_id="100", chat_type="group",
        trigger_message="hello", trigger_type="passive_tick", reason="mentioned",
    )


def _make_formatter():
    cfg = MagicMock()
    cfg.bot_uin = "12345"
    formatter = MagicMock(spec=ResponseFormatter)
    formatter.format_system_prompt.return_value = "You are a bot"
    formatter.format_response_prompt.return_value = "Reply in JSON"
    return formatter


class TestContentGenerator:
    def test_generate_success(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = '[{"content": "hello!", "mention_user_id": null, "reply_to_message_id": null}]'
        gen = ContentGenerator(llm, _make_formatter())
        plan = _make_plan()
        results = gen.generate([plan])
        assert len(results) == 1
        assert results[0].content == "hello!"

    def test_generate_with_extra_text(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = 'Here is the response:\n[{"content": "hi there!"}]\nEnd.'
        gen = ContentGenerator(llm, _make_formatter())
        results = gen.generate([_make_plan()])
        assert len(results) == 1
        assert results[0].content == "hi there!"

    def test_generate_empty_array(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = '[]'
        gen = ContentGenerator(llm, _make_formatter())
        results = gen.generate([_make_plan()])
        assert len(results) == 0

    def test_generate_invalid_json(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = 'not json at all'
        gen = ContentGenerator(llm, _make_formatter())
        results = gen.generate([_make_plan()])
        assert len(results) == 0

    def test_generate_llm_error_raises(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.side_effect = LLMError("timeout")
        gen = ContentGenerator(llm, _make_formatter())
        with pytest.raises(LLMError):
            gen.generate([_make_plan()])

    def test_generate_missing_fields(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = '[{"bad_field": "value"}]'
        gen = ContentGenerator(llm, _make_formatter())
        results = gen.generate([_make_plan()])
        assert len(results) == 0

    def test_generate_multiple_plans(self):
        llm = MagicMock(spec=LLMClient)
        llm.chat_text.return_value = '[{"content": "reply"}]'
        gen = ContentGenerator(llm, _make_formatter())
        plans = [_make_plan(f"a-{i}") for i in range(3)]
        results = gen.generate(plans)
        assert len(results) == 3
