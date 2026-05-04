import json
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from conf.schema import BotConfig
from infra.llm_client import LLMClient
from memory.concentrator import ConcentrateJob
from memory.long_term import LongTermMemory
from memory.schemas import MemoryType
from memory.short_term import ShortTermMemory
from memory.schemas import Message


def _msg(msg_id: str, content: str, user: str = "Alice") -> Message:
    return Message(
        message_id=msg_id, chat_type="group", chat_id="100",
        user_id="200", user_nickname=user, group_nickname=user,
        content=content, timestamp=datetime.now(),
    )


def _concentrate_response(entries=None):
    if entries is None:
        entries = [
            {
                "memory_type": "event",
                "summary": "Alice said hello",
                "importance": 5,
                "confidence": 0.9,
                "keywords": ["alice", "hello"],
                "source_message_ids": ["m1"],
            }
        ]
    return json.dumps({"entries": entries})


def _make_job(tmp_db_path: str, llm_response: str = ""):
    cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
    cfg.memory.pending_threshold = 5
    llm = MagicMock(spec=LLMClient)
    llm.chat_text.return_value = llm_response or _concentrate_response()
    long_term = LongTermMemory(tmp_db_path)
    job = ConcentrateJob(llm, long_term, cfg)
    return job, llm, long_term


class TestConcentrateJob:
    def test_run_success(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path)
        chat = ShortTermMemory("100")
        chat.add_incoming(_msg("m1", "hello"))
        chat.add_incoming(_msg("m2", "how are you"))
        chat.consume_unread()

        result = job.run(chat)
        assert result is True
        entries = long_term.search("", chat_id="100")
        assert len(entries) == 1
        assert "Alice" in entries[0].summary

    def test_run_empty_chat(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path)
        chat = ShortTermMemory("100")
        result = job.run(chat)
        assert result is True
        llm.chat_text.assert_not_called()

    def test_run_llm_failure(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path)
        llm.chat_text.side_effect = Exception("LLM error")
        chat = ShortTermMemory("100")
        chat.add_incoming(_msg("m1", "hello"))
        chat.consume_unread()

        result = job.run(chat)
        assert result is False
        # Messages should be preserved in read
        assert len(chat.get_read()) > 0

    def test_run_invalid_json(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path, llm_response="not valid json at all")
        chat = ShortTermMemory("100")
        chat.add_incoming(_msg("m1", "hello"))
        chat.consume_unread()

        result = job.run(chat)
        assert result is False

    def test_run_rotates_read_to_pending(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path)
        chat = ShortTermMemory("100")
        for i in range(10):
            chat.add_incoming(_msg(f"m{i}", f"message {i}"))
        chat.consume_unread()

        job.run(chat)
        # read should be empty after successful concentrate
        assert len(chat.get_read()) == 0
        # pending should have recent messages (up to pending_threshold)
        assert len(chat.get_pending()) <= job.config.memory.pending_threshold

    def test_run_clears_old_pending(self, tmp_db_path):
        job, llm, long_term = _make_job(tmp_db_path)
        chat = ShortTermMemory("100")
        # Add old pending messages
        for i in range(5):
            chat.add_incoming(_msg(f"old{i}", f"old message {i}"))
        chat.consume_unread()
        chat.rotate_read_to_pending()
        # Add new read messages
        for i in range(5):
            chat.add_incoming(_msg(f"new{i}", f"new message {i}"))
        chat.consume_unread()

        job.run(chat)
        # Old pending should be cleared, new pending should have recent read messages
        assert len(chat.get_pending()) <= job.config.memory.pending_threshold

    def test_run_multiple_entries(self, tmp_db_path):
        entries = [
            {"memory_type": "event", "summary": "event1", "importance": 5, "confidence": 0.9,
             "keywords": ["e1"], "source_message_ids": ["m1"]},
            {"memory_type": "fact", "summary": "fact1", "importance": 8, "confidence": 0.7,
             "keywords": ["f1"], "source_message_ids": ["m2"]},
        ]
        job, llm, long_term = _make_job(tmp_db_path, llm_response=_concentrate_response(entries))
        chat = ShortTermMemory("100")
        chat.add_incoming(_msg("m1", "hello"))
        chat.add_incoming(_msg("m2", "world"))
        chat.consume_unread()

        result = job.run(chat)
        assert result is True
        all_entries = long_term.search("", chat_id="100")
        assert len(all_entries) == 2

    def test_parse_output_with_extra_text(self):
        raw = 'Here is the result:\n{"entries": [{"memory_type": "event", "summary": "test", "importance": 5, "confidence": 0.9, "keywords": ["a"], "source_message_ids": ["m1"]}]}\nDone.'
        output = ConcentrateJob._parse_output(raw)
        assert output is not None
        assert len(output.entries) == 1
        assert output.entries[0].summary == "test"

    def test_parse_output_invalid(self):
        assert ConcentrateJob._parse_output("no json here") is None
        assert ConcentrateJob._parse_output("") is None
