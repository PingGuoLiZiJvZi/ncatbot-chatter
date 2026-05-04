import threading
import pytest
from infra.raw_message_log import RawMessageLog


class TestRawMessageLog:
    def test_insert_new(self, tmp_db_path):
        log = RawMessageLog(tmp_db_path)
        assert log.insert_if_new("msg-001") is True
        log.close()

    def test_insert_duplicate(self, tmp_db_path):
        log = RawMessageLog(tmp_db_path)
        assert log.insert_if_new("msg-001") is True
        assert log.insert_if_new("msg-001") is False
        log.close()

    def test_insert_multiple_different(self, tmp_db_path):
        log = RawMessageLog(tmp_db_path)
        assert log.insert_if_new("msg-001") is True
        assert log.insert_if_new("msg-002") is True
        assert log.insert_if_new("msg-003") is True
        log.close()

    def test_cleanup_removes_old(self, tmp_db_path):
        import sqlite3
        from datetime import datetime, timedelta
        log = RawMessageLog(tmp_db_path)
        # Insert with old timestamp
        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        log._conn.execute(
            "INSERT INTO raw_message_log (message_id, received_at) VALUES (?, ?)",
            ("old-msg", old_time),
        )
        log._conn.commit()
        assert log.insert_if_new("new-msg") is True
        deleted = log.cleanup(ttl_days=7)
        assert deleted == 1
        log.close()

    def test_cleanup_preserves_recent(self, tmp_db_path):
        log = RawMessageLog(tmp_db_path)
        log.insert_if_new("recent-msg")
        deleted = log.cleanup(ttl_days=7)
        assert deleted == 0
        log.close()

    def test_concurrent_insert(self, tmp_db_path):
        log = RawMessageLog(tmp_db_path)
        results = []
        lock = threading.Lock()

        def insert(msg_id):
            r = log.insert_if_new(msg_id)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=insert, args=("msg-concurrent",)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 1  # only one should succeed
        log.close()
