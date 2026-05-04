import time
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from conf.schema import BotConfig
from core.emergency_brake import EmergencyBrake
from core.schemas import ActionPlan, ActionType, GeneratedAction, Priority
from core.state import StateEventQueue
from infra.action_log import ActionLog
from infra.bot_adapter import BotAdapter, SendResult, SendStatus
from ui.sender import DelaySendScheduler


def _make_config() -> BotConfig:
    cfg = BotConfig(bot_uin="12345", root_uin="99999", api_key="sk-test")
    cfg.send.passive_delay_min = 0.01
    cfg.send.passive_delay_max = 0.05
    cfg.send.active_delay_min = 0.01
    cfg.send.active_delay_max = 0.05
    return cfg


def _make_plan(action_id: str, priority: Priority = Priority.P0) -> ActionPlan:
    return ActionPlan(
        action_id=action_id, action_type=ActionType.PASSIVE_REPLY,
        priority=priority, chat_id="100", chat_type="group",
        trigger_message="hello", trigger_type="passive_tick", reason="test",
    )


def _make_action(action_id: str, content: str = "reply", priority: Priority = Priority.P0) -> GeneratedAction:
    return GeneratedAction(plan=_make_plan(action_id, priority), content=content)


def _mock_group_send(chat_id, content, action_id=""):
    return SendResult(action_id=action_id, status=SendStatus.SENT, latency_ms=50)


def _make_scheduler(tmp_db_path: str):
    cfg = _make_config()
    adapter = MagicMock(spec=BotAdapter)
    adapter.send_group_msg.side_effect = _mock_group_send
    action_log = ActionLog(tmp_db_path)
    brake = EmergencyBrake(cfg)
    state_events = StateEventQueue()
    scheduler = DelaySendScheduler(adapter, action_log, brake, state_events, cfg)
    return scheduler, adapter, action_log, state_events


class TestDelaySendScheduler:
    def test_schedule_and_send(self, tmp_db_path):
        scheduler, adapter, action_log, state_events = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        action_log.record_planned([action.plan])
        action_log.record_generated([action])
        action_log.record_scheduled([action])

        scheduler.schedule(action, delay=0.05)
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        adapter.send_group_msg.assert_called_once()
        assert action_log.get_status("a-001") == "sent"

    def test_schedule_many(self, tmp_db_path):
        scheduler, adapter, action_log, _ = _make_scheduler(tmp_db_path)
        actions = [_make_action(f"a-{i}") for i in range(3)]
        for a in actions:
            action_log.record_planned([a.plan])
            action_log.record_generated([a])
            action_log.record_scheduled([a])

        scheduler.schedule_many(actions)
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        assert adapter.send_group_msg.call_count == 3

    def test_has_pending(self, tmp_db_path):
        scheduler, _, _, _ = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        scheduler.schedule(action, delay=10)
        assert scheduler.has_pending("100") is True
        assert scheduler.has_pending("999") is False

    def test_stop_drain_false(self, tmp_db_path):
        scheduler, adapter, action_log, _ = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        action_log.record_planned([action.plan])
        scheduler.schedule(action, delay=10)
        scheduler.stop(drain=False)
        adapter.send_group_msg.assert_not_called()

    def test_stop_drain_true_sends_immediate(self, tmp_db_path):
        scheduler, adapter, action_log, _ = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        action_log.record_planned([action.plan])
        action_log.record_generated([action])
        action_log.record_scheduled([action])
        # Schedule with delay=0 so it's immediately ready
        scheduler.schedule(action, delay=0)
        time.sleep(0.05)
        scheduler.stop(drain=True)
        adapter.send_group_msg.assert_called_once()

    def test_mark_as_sending_idempotent(self, tmp_db_path):
        scheduler, adapter, action_log, _ = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        action_log.record_planned([action.plan])
        action_log.record_generated([action])
        action_log.record_scheduled([action])

        # Schedule same action twice
        scheduler.schedule(action, delay=0.05)
        scheduler.schedule(action, delay=0.05)
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        # Should only send once due to mark_as_sending idempotency
        assert adapter.send_group_msg.call_count == 1

    def test_state_event_emitted(self, tmp_db_path):
        scheduler, adapter, action_log, state_events = _make_scheduler(tmp_db_path)
        action = _make_action("a-001")
        action_log.record_planned([action.plan])
        action_log.record_generated([action])
        action_log.record_scheduled([action])

        scheduler.schedule(action, delay=0.05)
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        events = state_events.drain()
        assert len(events) == 1
        assert events[0].event_type.value == "MESSAGE_SENT"
