from __future__ import annotations

import logging
import queue
from datetime import datetime
from typing import TYPE_CHECKING

from conf.schema import BotConfig
from core.activity_curve import ActivityCurve
from core.schemas import (
    ChatState,
    RuntimeMode,
    StateEvent,
    StateEventType,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BotState:
    def __init__(self, config: BotConfig, activity_curve: ActivityCurve):
        self.config = config
        self.activity_curve = activity_curve

        self.mode: RuntimeMode = RuntimeMode.STOPPED
        self.last_tick_at: datetime | None = None

        self.valence: float = 0.0
        self.energy: float = 1.0
        self.social_battery: float = 1.0
        self.interest: float = 0.5

        self.current_hour: int = 0
        self.activity_weight: float = 0.0
        self.per_chat: dict[str, ChatState] = {}
        self.cycle_count: int = 0

        self._consecutive_llm_failures: int = 0

    def tick(self, now: datetime) -> None:
        if self.last_tick_at is None:
            self.last_tick_at = now
            self.current_hour = now.hour
            self.activity_weight = self.activity_curve.get_weight(now.hour)
            self.cycle_count += 1
            return

        dt_seconds = (now - self.last_tick_at).total_seconds()
        if dt_seconds <= 0:
            return

        self._update_valence(dt_seconds)
        self._update_energy(dt_seconds)
        self._update_social_battery(dt_seconds)

        self.current_hour = now.hour
        self.activity_weight = self.activity_curve.get_weight(now.hour)
        self.last_tick_at = now
        self.cycle_count += 1

    def _update_valence(self, dt_seconds: float) -> None:
        regression = self.config.emotion.valence_regression * (dt_seconds / 60)
        if self.valence > 0:
            self.valence = max(0.0, self.valence - regression)
        elif self.valence < 0:
            self.valence = min(0.0, self.valence + regression)

    def _update_energy(self, dt_seconds: float) -> None:
        dt_hours = dt_seconds / 3600
        regen_rate = self.config.emotion.energy_regen_per_hour
        if self.activity_curve.is_sleeping(self.current_hour):
            regen_rate *= self.config.emotion.sleep_regen_multiplier
        self.energy = min(1.0, self.energy + regen_rate * dt_hours)

    def _update_social_battery(self, dt_seconds: float) -> None:
        dt_hours = dt_seconds / 3600
        self.social_battery = min(1.0, self.social_battery + 0.05 * dt_hours)

    def apply(self, event: StateEvent) -> None:
        match event.event_type:
            case StateEventType.MESSAGE_SENT:
                self.energy = max(0.0, self.energy - self.config.emotion.energy_step)
                self.social_battery = max(0.0, self.social_battery - self.config.emotion.energy_step)
            case StateEventType.MESSAGE_FAILED:
                pass
            case StateEventType.LLM_FAILED:
                self._consecutive_llm_failures += 1
                if self._consecutive_llm_failures >= self.config.llm.max_consecutive_failures:
                    self.transition(RuntimeMode.DEGRADED)
            case StateEventType.LLM_RECOVERED:
                self._consecutive_llm_failures = 0
                self.transition(RuntimeMode.RUNNING)
            case StateEventType.MODE_CHANGED:
                new_mode = event.payload.get("mode")
                if new_mode and isinstance(new_mode, RuntimeMode):
                    self.transition(new_mode)
                elif new_mode and isinstance(new_mode, str):
                    try:
                        self.transition(RuntimeMode(new_mode))
                    except ValueError:
                        logger.warning("Invalid mode in event: %s", new_mode)
            case StateEventType.EMOTION_SHIFTED:
                dv = event.payload.get("valence_delta", 0)
                di = event.payload.get("interest_delta", 0)
                self.valence = max(-1.0, min(1.0, self.valence + dv))
                self.interest = max(0.0, min(1.0, self.interest + di))

    _VALID_TRANSITIONS = {
        RuntimeMode.STOPPED: {RuntimeMode.STARTING},
        RuntimeMode.STARTING: {RuntimeMode.RUNNING, RuntimeMode.ERROR},
        RuntimeMode.RUNNING: {RuntimeMode.PASSIVE_ONLY, RuntimeMode.PAUSED, RuntimeMode.DEGRADED, RuntimeMode.ERROR, RuntimeMode.STOPPING},
        RuntimeMode.PASSIVE_ONLY: {RuntimeMode.RUNNING, RuntimeMode.PAUSED, RuntimeMode.DEGRADED, RuntimeMode.ERROR, RuntimeMode.STOPPING},
        RuntimeMode.PAUSED: {RuntimeMode.RUNNING, RuntimeMode.PASSIVE_ONLY, RuntimeMode.STOPPING, RuntimeMode.ERROR},
        RuntimeMode.DEGRADED: {RuntimeMode.RUNNING, RuntimeMode.PASSIVE_ONLY, RuntimeMode.ERROR, RuntimeMode.STOPPING},
        RuntimeMode.ERROR: {RuntimeMode.RUNNING, RuntimeMode.PASSIVE_ONLY, RuntimeMode.STOPPING, RuntimeMode.STARTING},
        RuntimeMode.STOPPING: {RuntimeMode.STOPPED},
    }

    def transition(self, new_mode: RuntimeMode) -> None:
        valid = self._VALID_TRANSITIONS.get(self.mode, set())
        if new_mode not in valid:
            logger.warning("Invalid transition: %s -> %s", self.mode.value, new_mode.value)
            return
        old = self.mode
        self.mode = new_mode
        logger.info("Mode transition: %s -> %s", old.value, new_mode.value)

    def get_chat_state(self, chat_id: str) -> ChatState:
        if chat_id not in self.per_chat:
            self.per_chat[chat_id] = ChatState(chat_id=chat_id)
        return self.per_chat[chat_id]


class StateEventQueue:
    def __init__(self):
        self._queue: queue.Queue[StateEvent] = queue.Queue()

    def put(self, event: StateEvent) -> None:
        self._queue.put(event)

    def drain(self) -> list[StateEvent]:
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events
