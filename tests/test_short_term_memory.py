import threading
from datetime import datetime
import pytest
from memory.short_term import ShortTermMemory
from memory.schemas import Message, SelfMessage


def _make_msg(msg_id: str, content: str = "hello") -> Message:
    return Message(
        message_id=msg_id,
        chat_type="group",
        chat_id="123",
        user_id="456",
        user_nickname="test",
        group_nickname="test",
        content=content,
        timestamp=datetime.now(),
    )


def _make_self_msg(action_id: str) -> SelfMessage:
    return SelfMessage(
        chat_type="group",
        chat_id="123",
        content="reply",
        timestamp=datetime.now(),
        action_id=action_id,
    )


class TestShortTermMemory:
    def test_add_incoming_and_consume(self):
        stm = ShortTermMemory("123")
        stm.add_incoming(_make_msg("m1"))
        stm.add_incoming(_make_msg("m2"))
        assert stm.get_unread_count() == 2

        unread = stm.consume_unread()
        assert len(unread) == 2
        assert stm.get_unread_count() == 0

    def test_consume_unread_atomic(self):
        stm = ShortTermMemory("123")
        for i in range(100):
            stm.add_incoming(_make_msg(f"m-{i}"))

        results = []
        lock = threading.Lock()

        def consume():
            r = stm.consume_unread()
            with lock:
                results.append(len(r))

        threads = [threading.Thread(target=consume) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 100

    def test_consume_moves_to_read(self):
        stm = ShortTermMemory("123")
        stm.add_incoming(_make_msg("m1"))
        stm.consume_unread()
        assert len(stm.get_read()) == 1

    def test_rotate_read_to_pending(self):
        stm = ShortTermMemory("123")
        stm.add_incoming(_make_msg("m1"))
        stm.consume_unread()
        stm.rotate_read_to_pending()
        assert len(stm.get_read()) == 0
        assert len(stm.get_pending()) == 1

    def test_clear_pending(self):
        stm = ShortTermMemory("123")
        stm.add_incoming(_make_msg("m1"))
        stm.consume_unread()
        stm.rotate_read_to_pending()
        stm.clear_pending()
        assert len(stm.get_pending()) == 0

    def test_should_concentrate(self):
        stm = ShortTermMemory("123")
        for i in range(15):
            stm.add_incoming(_make_msg(f"m-{i}"))
        stm.consume_unread()
        assert stm.should_concentrate(threshold=12) is True
        assert stm.should_concentrate(threshold=20) is False

    def test_add_self_sent(self):
        stm = ShortTermMemory("123")
        stm.add_self_sent(_make_self_msg("a-001"))
        assert len(stm._self_sent) == 1

    def test_concurrent_add_incoming(self):
        stm = ShortTermMemory("123")

        def add(i):
            stm.add_incoming(_make_msg(f"m-{i}"))

        threads = [threading.Thread(target=add, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert stm.get_unread_count() == 100
