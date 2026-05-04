import queue
from unittest.mock import MagicMock
from datetime import datetime
import pytest
from infra.message_ingestor import MessageIngestor
from infra.raw_message_log import RawMessageLog
from memory.manager import MemoryManager


def _make_group_event(message_id="msg-001", group_id="100", user_id="200", text="hello"):
    event = MagicMock()
    event.__class__.__name__ = "GroupMessage"
    event.message_id = message_id
    event.group_id = group_id
    event.user_id = user_id
    event.message = [{"type": "text", "data": {"text": text}}]
    event.sender = {"nickname": "test_user", "card": "test_card"}
    return event


def _make_private_event(message_id="msg-p001", user_id="300", text="hi"):
    event = MagicMock()
    event.__class__.__name__ = "PrivateMessage"
    event.message_id = message_id
    event.user_id = user_id
    event.message = [{"type": "text", "data": {"text": text}}]
    event.sender = {"nickname": "private_user"}
    return event


class TestMessageIngestor:
    def _make_ingestor(self, tmp_db_path):
        q = queue.Queue()
        memory = MemoryManager()
        raw_log = RawMessageLog(tmp_db_path)
        return MessageIngestor(q, memory, raw_log), q, memory, raw_log

    def test_parse_group_message(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        event = _make_group_event()
        msg = ing._parse(event)
        assert msg is not None
        assert msg.chat_type == "group"
        assert msg.chat_id == "100"
        assert msg.content == "hello"
        raw_log.close()

    def test_parse_private_message(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        event = _make_private_event()
        msg = ing._parse(event)
        assert msg is not None
        assert msg.chat_type == "private"
        assert msg.chat_id == "300"
        assert msg.content == "hi"
        raw_log.close()

    def test_parse_no_text(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        event = _make_group_event(text="")
        event.message = [{"type": "image", "data": {"url": "http://..."}}]
        msg = ing._parse(event)
        assert msg is None
        raw_log.close()

    def test_drain_processes_messages(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        for i in range(5):
            q.put(_make_group_event(message_id=f"msg-{i}", text=f"text-{i}"))
        count = ing.drain()
        assert count == 5
        raw_log.close()

    def test_drain_deduplicates(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        q.put(_make_group_event(message_id="dup-001", text="first"))
        q.put(_make_group_event(message_id="dup-001", text="duplicate"))
        count = ing.drain()
        assert count == 1
        raw_log.close()

    def test_drain_max_items(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        for i in range(10):
            q.put(_make_group_event(message_id=f"msg-{i}", text=f"text-{i}"))
        count = ing.drain(max_items=3)
        assert count == 3
        assert q.qsize() == 7
        raw_log.close()

    def test_drain_empty_queue(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        count = ing.drain()
        assert count == 0
        raw_log.close()

    def test_drain_writes_to_memory(self, tmp_db_path):
        ing, q, mem, raw_log = self._make_ingestor(tmp_db_path)
        q.put(_make_group_event(message_id="mem-001", group_id="500", text="hello"))
        ing.drain()
        chat = mem.get_chat("500")
        assert chat is not None
        assert chat.get_unread_count() == 1
        raw_log.close()
