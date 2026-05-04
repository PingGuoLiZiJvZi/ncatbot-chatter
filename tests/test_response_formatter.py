from unittest.mock import MagicMock
import pytest
from generation.formatter import ResponseFormatter
from memory.schemas import MemoryContext, MemoryEntry, MemoryType


class TestResponseFormatter:
    def _make_formatter(self):
        # Use real formatter with mock config
        cfg = MagicMock()
        cfg.bot_uin = "12345"
        formatter = ResponseFormatter.__new__(ResponseFormatter)
        formatter.config = cfg
        formatter._prompts = {
            "base_prompt": "You are a helpful bot.",
            "response_prompt": "Reply in JSON format.",
        }
        formatter._character = {"description": "A friendly chat bot."}
        return formatter

    def test_format_system_prompt(self):
        f = self._make_formatter()
        result = f.format_system_prompt()
        assert "A friendly chat bot" in result
        assert "You are a helpful bot" in result

    def test_format_system_prompt_with_emotion(self):
        f = self._make_formatter()
        result = f.format_system_prompt({"valence": 0.5, "energy": 0.8, "interest": 0.6})
        assert "0.50" in result
        assert "0.80" in result

    def test_format_memory_context_empty(self):
        f = self._make_formatter()
        ctx = MemoryContext()
        assert f.format_memory_context(ctx) == ""

    def test_format_memory_context_with_entries(self):
        f = self._make_formatter()
        ctx = MemoryContext(entries=[
            MemoryEntry(memory_type=MemoryType.EVENT, summary="User said hello"),
            MemoryEntry(memory_type=MemoryType.FACT, summary="User likes cats"),
        ])
        result = f.format_memory_context(ctx)
        assert "User said hello" in result
        assert "User likes cats" in result

    def test_format_chat_messages(self):
        from datetime import datetime
        from memory.short_term import ShortTermMemory
        from memory.schemas import Message

        f = self._make_formatter()
        chat = ShortTermMemory("100")
        chat.add_incoming(Message(
            message_id="m1", chat_type="group", chat_id="100",
            user_id="200", user_nickname="Alice", group_nickname="Alice",
            content="hello", timestamp=datetime.now(),
        ))
        chat.consume_unread()
        result = f.format_chat_messages([chat])
        assert "Alice" in result
        assert "hello" in result

    def test_format_response_prompt(self):
        f = self._make_formatter()
        assert "JSON" in f.format_response_prompt()
