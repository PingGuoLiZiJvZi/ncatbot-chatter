from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import datetime

from conf.schema import BotConfig
from core.orchestrator import Orchestrator
from core.schemas import RuntimeMode
from core.state import BotState
from infra.action_log import ActionLog
from infra.llm_client import LLMClient
from infra.raw_message_log import RawMessageLog
from memory.long_term import LongTermMemory
from memory.relationship import RelationshipGraph
from memory.entity import EntityProfile
from ui.sender import DelaySendScheduler

logger = logging.getLogger(__name__)


class MainLoop:
    def __init__(
        self,
        orchestrator: Orchestrator,
        state: BotState,
        config: BotConfig,
    ):
        self.orchestrator = orchestrator
        self.state = state
        self.config = config
        self._shutdown = threading.Event()
        self._wakeup = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.state.transition(RuntimeMode.STARTING)
        self.state.transition(RuntimeMode.RUNNING)
        self._thread = threading.Thread(target=self._run, daemon=True, name="mainloop")
        self._thread.start()
        logger.info("MainLoop started")

    def wake_up(self) -> None:
        """Called from event handlers to trigger immediate processing of P0 messages."""
        self._wakeup.set()

    def _run(self) -> None:
        passive_interval = self.config.loop.passive_interval
        active_interval = self.config.loop.active_interval
        concentrate_interval = self.config.loop.concentrate_interval

        last_active = 0.0
        last_concentrate = 0.0

        while not self._shutdown.is_set():
            now = time.time()

            self.orchestrator.run_passive_tick()

            if now - last_active >= active_interval:
                self.orchestrator.run_active_tick()
                last_active = now

            if now - last_concentrate >= concentrate_interval:
                self.orchestrator.run_concentrate_tick()
                last_concentrate = now

            # Wait for next tick, but wake up immediately if P0 message arrives
            self._wakeup.clear()
            self._shutdown.wait(timeout=passive_interval)
            if self._wakeup.is_set():
                logger.debug("Woken up by P0 message, skipping sleep")

    def stop(self) -> None:
        self._shutdown.set()
        self._wakeup.set()  # unblock wait
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("MainLoop stopped")


class ShutdownManager:
    def __init__(
        self,
        main_loop: MainLoop,
        sender: DelaySendScheduler,
        state: BotState,
        action_log: ActionLog,
        raw_log: RawMessageLog,
        long_term: LongTermMemory,
        relationship: RelationshipGraph,
        entity: EntityProfile,
        llm: LLMClient,
    ):
        self.main_loop = main_loop
        self.sender = sender
        self.state = state
        self.action_log = action_log
        self.raw_log = raw_log
        self.long_term = long_term
        self.relationship = relationship
        self.entity = entity
        self.llm = llm
        self._original_handlers: dict = {}

    def install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._original_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, self._handle_signal)
            except (OSError, ValueError):
                pass  # signal not available on this platform

    def _handle_signal(self, signum, frame):
        logger.info("Received signal %s, initiating shutdown", signum)
        self.shutdown(drain_pending=True)

    def shutdown(self, drain_pending: bool = True) -> None:
        logger.info("Shutdown sequence started")
        self.state.transition(RuntimeMode.STOPPING)

        self.main_loop.stop()
        self.sender.stop(drain=drain_pending)

        # Close all connections
        self.action_log.close()
        self.raw_log.close()
        self.long_term.close()
        self.relationship.close()
        self.entity.close()
        self.llm.close()

        self.state.transition(RuntimeMode.STOPPED)
        logger.info("Shutdown complete")
