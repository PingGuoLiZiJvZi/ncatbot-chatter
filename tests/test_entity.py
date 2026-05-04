import pytest
from memory.entity import EntityProfile


class TestEntityProfile:
    def test_upsert_and_get(self, tmp_db_path):
        ep = EntityProfile(tmp_db_path)
        ep.upsert("user_123", entity_type="user", display_name="Alice", summary="A friendly user")
        profile = ep.get("user_123")
        assert profile is not None
        assert profile["display_name"] == "Alice"
        assert profile["summary"] == "A friendly user"
        assert profile["entity_type"] == "user"

    def test_get_nonexistent(self, tmp_db_path):
        ep = EntityProfile(tmp_db_path)
        assert ep.get("nobody") is None

    def test_upsert_update_preserves_existing(self, tmp_db_path):
        ep = EntityProfile(tmp_db_path)
        ep.upsert("user_123", display_name="Alice", summary="Original summary")
        ep.upsert("user_123", display_name="", summary="Updated summary")
        profile = ep.get("user_123")
        assert profile["display_name"] == "Alice"  # preserved
        assert profile["summary"] == "Updated summary"  # updated

    def test_upsert_update_overwrite_name(self, tmp_db_path):
        ep = EntityProfile(tmp_db_path)
        ep.upsert("user_123", display_name="Alice")
        ep.upsert("user_123", display_name="Bob")
        profile = ep.get("user_123")
        assert profile["display_name"] == "Bob"
