from __future__ import annotations

import heapq
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from conf.schema import BotConfig
from core.emergency_brake import EmergencyBrake
from core.schemas import BrakeDecision, GeneratedAction, Priority, StateEvent, StateEventType
from core.state import StateEventQueue
from infra.action_log import ActionLog
from infra.bot_adapter import BotAdapter, SendResult

logger = logging.getLogger(__name__)


@dataclass
class ScheduledItem:
    fire_at: float
    action: GeneratedAction
    action_id: str = ""

    def __lt__(self, other: ScheduledItem) -> bool:
        return self.fire_at < other.fire_at


class DelaySendScheduler:
    def __init__(
        self,
        bot_adapter: BotAdapter,
        action_log: ActionLog,
        brake: EmergencyBrake,
        state_events: StateEventQueue,
        config: BotConfig,
    ):
        self.bot_adapter = bot_adapter
        self.action_log = action_log
        self.brake = brake
        self.state_events = state_events
        self.config = config
        self._heap: list[ScheduledItem] = []
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def schedule(self, action: GeneratedAction, delay: float | None = None) -> None:
        if delay is None:
            delay = self._calculate_delay(action)
        fire_at = time.time() + delay
        item = ScheduledItem(fire_at=fire_at, action=action, action_id=action.plan.action_id)
        with self._lock:
            heapq.heappush(self._heap, item)
        logger.debug("Scheduled action %s in %.1fs", action.plan.action_id, delay)

    def schedule_many(self, actions: list[GeneratedAction]) -> None:
        for a in actions:
            self.schedule(a)

    def has_pending(self, chat_id: str) -> bool:
        with self._lock:
            return any(item.action.plan.chat_id == chat_id for item in self._heap)

    def stop(self, drain: bool = False) -> None:
        self._shutdown.set()
        if drain:
            now = time.time()
            with self._lock:
                while self._heap and self._heap[0].fire_at <= now:
                    item = heapq.heappop(self._heap)
                    self._execute_send(item)
                for item in self._heap:
                    self.action_log.record(item.action.plan, status="cancelled", reason="shutdown")
        else:
            with self._lock:
                for item in self._heap:
                    self.action_log.record(item.action.plan, status="cancelled", reason="shutdown")
                self._heap.clear()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._shutdown.is_set():
            with self._lock:
                if not self._heap:
                    next_fire = None
                else:
                    next_fire = self._heap[0].fire_at

            if next_fire is None:
                time.sleep(0.1)
                continue

            now = time.time()
            wait = max(0, next_fire - now)
            if wait > 0:
                self._shutdown.wait(timeout=min(wait, 1.0))
                continue

            with self._lock:
                if self._heap and self._heap[0].fire_at <= time.time():
                    item = heapq.heappop(self._heap)
                else:
                    continue

            self._execute_send(item)

    def _execute_send(self, item: ScheduledItem) -> None:
        action = item.action
        plan = action.plan

        if not self.action_log.mark_as_sending(plan.action_id):
            logger.warning("Failed to mark %s as sending (already processed)", plan.action_id)
            return

        logger.info("Sending %s to %s (%s): %s", plan.action_id, plan.chat_id, plan.chat_type, action.content[:50])

        if plan.chat_type == "group":
            result = self.bot_adapter.send_group_msg(
                plan.chat_id, action.content, action_id=plan.action_id
            )
        else:
            result = self.bot_adapter.send_private_msg(
                plan.chat_id, action.content, action_id=plan.action_id
            )

        self.action_log.record_send_result(result)

        event_type = StateEventType.MESSAGE_SENT if result.status.value == "SENT" else StateEventType.MESSAGE_FAILED
        self.state_events.put(StateEvent(
            event_type=event_type,
            payload={"action_id": plan.action_id, "chat_id": plan.chat_id},
            timestamp=datetime.now(),
        ))

    def _calculate_delay(self, action: GeneratedAction) -> float:
        cfg = self.config.send
        if action.plan.priority == Priority.P0:
            delay = max(cfg.passive_delay_min, min(cfg.passive_delay_max,
                random.gauss(cfg.passive_delay_mu, cfg.passive_delay_sigma)))
        elif action.plan.priority == Priority.P1:
            delay = max(cfg.passive_delay_min, min(cfg.passive_delay_max,
                random.gauss(cfg.passive_delay_mu, cfg.passive_delay_sigma)))
        else:
            delay = max(cfg.active_delay_min, min(cfg.active_delay_max,
                random.gauss(cfg.active_delay_mu, cfg.active_delay_sigma)))
        return delay
