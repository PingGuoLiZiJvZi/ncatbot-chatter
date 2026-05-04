from datetime import datetime, timedelta
import pytest
from memory.long_term import LongTermMemory
from memory.schemas import MemoryEntry, MemoryType


def _entry(
    summary: str = "test",
    chat_id: str = "100",
    memory_type: MemoryType = MemoryType.EVENT,
    importance: int = 5,
    keywords: str = "",
    expires_at: str | None = None,
    is_active: int = 1,
) -> MemoryEntry:
    return MemoryEntry(
        memory_type=memory_type,
        chat_type="group",
        chat_id=chat_id,
        timestamp=datetime.now().isoformat(),
        importance=importance,
        summary=summary,
        keywords=keywords,
        expires_at=expires_at,
        is_active=is_active,
    )


class TestLongTermMemory:
    def test_add_returns_id(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        eid = mem.add(_entry("hello"))
        assert eid is not None
        assert eid >= 1

    def test_search_by_keyword(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(summary="Alice likes cats", keywords="alice,cats"))
        mem.add(_entry(summary="Bob likes dogs", keywords="bob,dogs"))
        results = mem.search("cats")
        assert len(results) == 1
        assert "cats" in results[0].summary

    def test_search_by_chat_id(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(chat_id="100", summary="group1"))
        mem.add(_entry(chat_id="200", summary="group2"))
        results = mem.search("", chat_id="100")
        assert len(results) == 1
        assert results[0].chat_id == "100"

    def test_search_limit(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        for i in range(10):
            mem.add(_entry(summary=f"entry {i}"))
        results = mem.search("", limit=3)
        assert len(results) == 3

    def test_search_exclude_inactive(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(summary="active", is_active=1))
        mem.add(_entry(summary="inactive", is_active=0))
        active = mem.search("", include_inactive=False)
        assert all(e.is_active == 1 for e in active)
        all_entries = mem.search("", include_inactive=True)
        assert len(all_entries) == 2

    def test_mark_accessed(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        eid = mem.add(_entry("test"))
        mem.mark_accessed([eid])
        results = mem.search("test")
        assert results[0].access_count == 1

    def test_expire_old_archive(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        past = (datetime.now() - timedelta(days=1)).isoformat()
        future = (datetime.now() + timedelta(days=1)).isoformat()
        eid_old = mem.add(_entry(summary="old", expires_at=past))
        eid_new = mem.add(_entry(summary="new", expires_at=future))
        count = mem.expire_old(now=datetime.now(), archive=True)
        assert count == 1
        results = mem.search("old", include_inactive=True)
        assert results[0].is_active == 0
        results = mem.search("new")
        assert len(results) == 1

    def test_expire_old_delete(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        past = (datetime.now() - timedelta(days=1)).isoformat()
        mem.add(_entry(summary="old", expires_at=past))
        count = mem.expire_old(now=datetime.now(), archive=False)
        assert count == 1
        results = mem.search("old", include_inactive=True)
        assert len(results) == 0

    def test_merge_similar(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(summary="Alice likes cats", keywords="alice,cats", importance=5))
        new_entry = _entry(summary="Alice has a cat", keywords="alice,cats", importance=7)
        merged_id = mem.merge_similar(new_entry)
        assert merged_id is not None
        results = mem.search("alice")
        assert len(results) == 1
        assert results[0].importance == 7

    def test_merge_similar_no_match(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(summary="Bob likes dogs", keywords="bob,dogs"))
        new_entry = _entry(summary="Alice likes cats", keywords="alice,cats")
        merged_id = mem.merge_similar(new_entry)
        assert merged_id is None

    def test_get_context(self, tmp_db_path):
        mem = LongTermMemory(tmp_db_path)
        mem.add(_entry(summary="hello world", keywords="hello"))
        ctx = mem.get_context("100", "hello")
        assert len(ctx.entries) == 1
        assert ctx.chat_id == "100"
        assert ctx.query == "hello"
        # check access_count incremented
        assert ctx.entries[0].access_count == 1
