import pytest
from memory.relationship import RelationshipGraph


class TestRelationshipGraph:
    def test_upsert_and_get(self, tmp_db_path):
        g = RelationshipGraph(tmp_db_path)
        g.upsert("alice", "bob", rel_type="friend", intimacy=0.8, note="close friends")
        rel = g.get("alice", "bob")
        assert rel is not None
        assert rel["rel_type"] == "friend"
        assert rel["intimacy"] == 0.8
        assert rel["note"] == "close friends"

    def test_get_nonexistent(self, tmp_db_path):
        g = RelationshipGraph(tmp_db_path)
        assert g.get("alice", "bob") is None

    def test_upsert_update(self, tmp_db_path):
        g = RelationshipGraph(tmp_db_path)
        g.upsert("alice", "bob", rel_type="acquaintance", intimacy=0.2)
        g.upsert("alice", "bob", rel_type="friend", intimacy=0.9, note="best friends")
        rel = g.get("alice", "bob")
        assert rel["rel_type"] == "friend"
        assert rel["intimacy"] == 0.9

    def test_get_all_for(self, tmp_db_path):
        g = RelationshipGraph(tmp_db_path)
        g.upsert("alice", "bob", rel_type="friend", intimacy=0.8)
        g.upsert("alice", "charlie", rel_type="colleague", intimacy=0.3)
        g.upsert("bob", "charlie", rel_type="stranger", intimacy=0.1)
        rels = g.get_all_for("alice")
        assert len(rels) == 2
        partners = {r["entity_b"] if r["entity_a"] == "alice" else r["entity_a"] for r in rels}
        assert partners == {"bob", "charlie"}

    def test_get_all_for_empty(self, tmp_db_path):
        g = RelationshipGraph(tmp_db_path)
        assert g.get_all_for("nobody") == []
