from datetime import datetime, timedelta
import pytest
from conf.schema import BotConfig, ActivityConfig
from core.activity_curve import ActivityCurve
from core.state import BotState, StateEventQueue
from core.schemas import RuntimeMode, StateEvent, StateEventType


def _make_config() -> BotConfig:
    return BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")


def _make_state(config: BotConfig | None = None) -> BotState:
    cfg = config or _make_config()
    ac = ActivityCurve(cfg.activity)
    return BotState(cfg, ac)


class TestBotStateTick:
    def test_first_tick_sets_last_tick_at(self):
        bs = _make_state()
        now = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(now)
        assert bs.last_tick_at == now

    def test_tick_updates_emotions(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.valence = 0.5
        t1 = t0 + timedelta(seconds=60)
        bs.tick(t1)
        assert bs.valence < 0.5  # regressed
        assert bs.valence >= 0.0  # didn't cross zero

    def test_valence_regression_negative(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.valence = -0.5
        t1 = t0 + timedelta(seconds=60)
        bs.tick(t1)
        assert bs.valence > -0.5
        assert bs.valence <= 0.0

    def test_valence_never_crosses_zero(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.valence = 0.01
        # Run many ticks
        for i in range(1, 1000):
            bs.tick(t0 + timedelta(seconds=i * 60))
        assert bs.valence >= 0.0

    def test_energy_recovery(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.energy = 0.2
        t1 = t0 + timedelta(hours=6)
        bs.tick(t1)
        assert bs.energy > 0.2

    def test_energy_recovery_faster_during_sleep(self):
        cfg = _make_config()
        ac = ActivityCurve(cfg.activity)
        bs = BotState(cfg, ac)

        # Non-sleep recovery
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.energy = 0.2
        t1 = t0 + timedelta(hours=1)
        bs.tick(t1)
        non_sleep_energy = bs.energy

        # Sleep recovery
        bs2 = _make_state()
        t0_sleep = datetime(2026, 5, 4, 2, 0, 0)
        bs2.tick(t0_sleep)
        bs2.energy = 0.2
        t1_sleep = t0_sleep + timedelta(hours=1)
        bs2.tick(t1_sleep)
        sleep_energy = bs2.energy

        assert sleep_energy > non_sleep_energy

    def test_energy_capped_at_1(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.energy = 0.99
        t1 = t0 + timedelta(hours=10)
        bs.tick(t1)
        assert bs.energy <= 1.0

    def test_tick_with_dt_zero(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        bs.tick(t0)  # same time
        assert bs.valence == 0.0  # unchanged

    def test_activity_weight_updates(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        assert bs.activity_weight == bs.activity_curve.get_weight(12)

    def test_cycle_count_increments(self):
        bs = _make_state()
        t0 = datetime(2026, 5, 4, 12, 0, 0)
        bs.tick(t0)
        assert bs.cycle_count == 1
        bs.tick(t0 + timedelta(seconds=1))
        assert bs.cycle_count == 2


class TestBotStateApply:
    def test_apply_message_sent(self):
        bs = _make_state()
        initial_energy = bs.energy
        event = StateEvent(event_type=StateEventType.MESSAGE_SENT)
        bs.apply(event)
        assert bs.energy < initial_energy

    def test_apply_llm_failed_increments(self):
        bs = _make_state()
        event = StateEvent(event_type=StateEventType.LLM_FAILED)
        bs.apply(event)
        assert bs._consecutive_llm_failures == 1

    def test_apply_llm_failed_5_times_degraded(self):
        bs = _make_state()
        bs.mode = RuntimeMode.RUNNING
        for _ in range(5):
            bs.apply(StateEvent(event_type=StateEventType.LLM_FAILED))
        assert bs.mode == RuntimeMode.DEGRADED

    def test_apply_llm_recovered(self):
        bs = _make_state()
        bs.mode = RuntimeMode.DEGRADED
        bs._consecutive_llm_failures = 5
        bs.apply(StateEvent(event_type=StateEventType.LLM_RECOVERED))
        assert bs.mode == RuntimeMode.RUNNING
        assert bs._consecutive_llm_failures == 0

    def test_apply_mode_changed(self):
        bs = _make_state()
        bs.mode = RuntimeMode.RUNNING
        bs.apply(StateEvent(
            event_type=StateEventType.MODE_CHANGED,
            payload={"mode": RuntimeMode.PAUSED},
        ))
        assert bs.mode == RuntimeMode.PAUSED

    def test_apply_emotion_shifted(self):
        bs = _make_state()
        bs.valence = 0.0
        bs.apply(StateEvent(
            event_type=StateEventType.EMOTION_SHIFTED,
            payload={"valence_delta": 0.2, "interest_delta": 0.1},
        ))
        assert bs.valence == pytest.approx(0.2)
        assert bs.interest == pytest.approx(0.6)

    def test_apply_emotion_shifted_clamps(self):
        bs = _make_state()
        bs.valence = 0.9
        bs.apply(StateEvent(
            event_type=StateEventType.EMOTION_SHIFTED,
            payload={"valence_delta": 0.5},
        ))
        assert bs.valence == 1.0


class TestBotStateTransition:
    def test_stopped_to_starting(self):
        bs = _make_state()
        bs.transition(RuntimeMode.STARTING)
        assert bs.mode == RuntimeMode.STARTING

    def test_starting_to_running(self):
        bs = _make_state()
        bs.mode = RuntimeMode.STARTING
        bs.transition(RuntimeMode.RUNNING)
        assert bs.mode == RuntimeMode.RUNNING

    def test_invalid_transition_ignored(self):
        bs = _make_state()
        bs.transition(RuntimeMode.RUNNING)  # STOPPED -> RUNNING is invalid
        assert bs.mode == RuntimeMode.STOPPED

    def test_running_to_degraded(self):
        bs = _make_state()
        bs.mode = RuntimeMode.RUNNING
        bs.transition(RuntimeMode.DEGRADED)
        assert bs.mode == RuntimeMode.DEGRADED

    def test_degraded_to_running(self):
        bs = _make_state()
        bs.mode = RuntimeMode.DEGRADED
        bs.transition(RuntimeMode.RUNNING)
        assert bs.mode == RuntimeMode.RUNNING


class TestBotStateChatState:
    def test_get_chat_state_creates(self):
        bs = _make_state()
        cs = bs.get_chat_state("123")
        assert cs.chat_id == "123"

    def test_get_chat_state_returns_existing(self):
        bs = _make_state()
        cs1 = bs.get_chat_state("123")
        cs2 = bs.get_chat_state("123")
        assert cs1 is cs2


class TestStateEventQueue:
    def test_put_and_drain(self):
        q = StateEventQueue()
        e1 = StateEvent(event_type=StateEventType.MESSAGE_SENT)
        e2 = StateEvent(event_type=StateEventType.LLM_FAILED)
        q.put(e1)
        q.put(e2)
        events = q.drain()
        assert len(events) == 2

    def test_drain_empty(self):
        q = StateEventQueue()
        assert q.drain() == []

    def test_drain_clears_queue(self):
        q = StateEventQueue()
        q.put(StateEvent(event_type=StateEventType.MESSAGE_SENT))
        q.drain()
        assert q.drain() == []
