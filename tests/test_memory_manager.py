from datetime import datetime
import pytest
from memory.manager import MemoryManager
from memory.schemas import Message


def _make_msg(chat_id: str, msg_id: str, content: str = "hello") -> Message:
    return Message(
        message_id=msg_id,
        chat_type="group",
        chat_id=chat_id,
        user_id="456",
        user_nickname="test",
        group_nickname="test",
        content=content,
        timestamp=datetime.now(),
    )


class TestMemoryManager:
    def test_add_message_creates_chat(self):
        mm = MemoryManager()
        mm.add_message(_make_msg("100", "m1"))
        assert mm.get_chat("100") is not None

    def test_add_message_routes_to_correct_chat(self):
        mm = MemoryManager()
        mm.add_message(_make_msg("100", "m1"))
        mm.add_message(_make_msg("200", "m2"))
        mm.add_message(_make_msg("100", "m3"))
        assert mm.get_chat("100").get_unread_count() == 2
        assert mm.get_chat("200").get_unread_count() == 1

    def test_get_chat_nonexistent(self):
        mm = MemoryManager()
        assert mm.get_chat("999") is None

    def test_get_active_chats(self):
        mm = MemoryManager()
        mm.add_message(_make_msg("100", "m1"))
        mm.add_message(_make_msg("200", "m2"))
        active = mm.get_active_chats()
        assert len(active) == 2

    def test_get_active_chats_empty_after_consume(self):
        mm = MemoryManager()
        mm.add_message(_make_msg("100", "m1"))
        chat = mm.get_chat("100")
        chat.consume_unread()
        assert len(mm.get_active_chats()) == 0

    def test_get_all_chats(self):
        mm = MemoryManager()
        mm.add_message(_make_msg("100", "m1"))
        mm.add_message(_make_msg("200", "m2"))
        mm.add_message(_make_msg("300", "m3"))
        assert len(mm.get_all_chats()) == 3

    def test_get_or_create_chat(self):
        mm = MemoryManager()
        chat1 = mm.get_or_create_chat("100")
        chat2 = mm.get_or_create_chat("100")
        assert chat1 is chat2
