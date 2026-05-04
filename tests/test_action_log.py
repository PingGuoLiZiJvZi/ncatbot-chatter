import pytest
from datetime import datetime
from core.schemas import ActionPlan, ActionType, Priority, GeneratedAction
from infra.action_log import ActionLog
from infra.bot_adapter import SendResult, SendStatus


def _make_plan(action_id: str, priority: Priority = Priority.P0) -> ActionPlan:
    return ActionPlan(
        action_id=action_id,
        action_type=ActionType.PASSIVE_REPLY,
        priority=priority,
        chat_id="123",
        chat_type="group",
        trigger_message="hello",
        trigger_type="passive_tick",
        reason="mentioned",
    )


def _make_action(action_id: str, content: str = "reply") -> GeneratedAction:
    return GeneratedAction(plan=_make_plan(action_id), content=content, llm_raw='{"content":"reply"}')


class TestActionLog:
    def test_record_planned(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-001")
        log.record_planned([plan])
        assert log.get_status("a-001") == "planned"
        log.close()

    def test_record_generated(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-002")
        log.record_planned([plan])
        action = _make_action("a-002")
        log.record_generated([action])
        assert log.get_status("a-002") == "generated"
        log.close()

    def test_record_scheduled(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-003")
        log.record_planned([plan])
        action = _make_action("a-003")
        log.record_generated([action])
        log.record_scheduled([action])
        assert log.get_status("a-003") == "scheduled"
        log.close()

    def test_mark_as_sending(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-004")
        log.record_planned([plan])
        assert log.mark_as_sending("a-004") is True
        assert log.get_status("a-004") == "sending"
        log.close()

    def test_mark_as_sending_already_sent(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-005")
        log.record_planned([plan])
        log.mark_as_sending("a-005")
        result = SendResult(action_id="a-005", status=SendStatus.SENT, latency_ms=100)
        log.record_send_result(result)
        assert log.get_status("a-005") == "sent"
        assert log.mark_as_sending("a-005") is False
        log.close()

    def test_mark_as_sending_cancelled(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-006")
        log.record_planned([plan])
        log.record(plan, status="cancelled", reason="test")
        assert log.mark_as_sending("a-006") is False
        log.close()

    def test_record_send_result(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-007")
        log.record_planned([plan])
        log.mark_as_sending("a-007")
        result = SendResult(action_id="a-007", status=SendStatus.SENT, latency_ms=150)
        log.record_send_result(result)
        assert log.get_status("a-007") == "sent"
        log.close()

    def test_record_cancelled(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-008")
        log.record_planned([plan])
        log.record(plan, status="cancelled", reason="brake")
        assert log.get_status("a-008") == "cancelled"
        log.close()

    def test_record_failed(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-009")
        log.record_planned([plan])
        log.record(plan, status="failed", reason="timeout")
        assert log.get_status("a-009") == "failed"
        log.close()

    def test_record_batch(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plans = [_make_plan(f"b-{i}") for i in range(5)]
        log.record_planned(plans)
        log.record_batch(plans, status="cancelled", reason="llm_failed")
        for i in range(5):
            assert log.get_status(f"b-{i}") == "cancelled"
        log.close()

    def test_idempotent_planned(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("a-010")
        log.record_planned([plan])
        log.record_planned([plan])  # duplicate
        assert log.get_status("a-010") == "planned"
        log.close()

    def test_full_lifecycle(self, tmp_db_path):
        log = ActionLog(tmp_db_path)
        plan = _make_plan("life-001")
        log.record_planned([plan])
        assert log.get_status("life-001") == "planned"

        action = _make_action("life-001")
        log.record_generated([action])
        assert log.get_status("life-001") == "generated"

        log.record_scheduled([action])
        assert log.get_status("life-001") == "scheduled"

        assert log.mark_as_sending("life-001") is True
        assert log.get_status("life-001") == "sending"

        result = SendResult(action_id="life-001", status=SendStatus.SENT, latency_ms=200)
        log.record_send_result(result)
        assert log.get_status("life-001") == "sent"
        log.close()
