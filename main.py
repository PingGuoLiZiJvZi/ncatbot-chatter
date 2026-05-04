from __future__ import annotations

import logging
import queue
import sys

from conf.loader import ConfigLoader
from conf.schema import BotConfig
from core.activity_curve import ActivityCurve
from core.degraded_policy import DegradedReplyPolicy
from core.decision import DecisionEngine
from core.emergency_brake import EmergencyBrake
from core.main_loop import MainLoop, ShutdownManager
from core.orchestrator import Orchestrator
from core.passive_judge import PassiveReplyJudge
from core.active_gate import ActiveSpeakGate
from core.state import BotState, StateEventQueue
from generation.content_gen import ContentGenerator
from generation.formatter import ResponseFormatter
from infra.action_log import ActionLog
from infra.bot_adapter import BotAdapter
from infra.llm_client import LLMClient
from infra.message_ingestor import MessageIngestor
from infra.raw_message_log import RawMessageLog
from infra.logger import setup_logger
from memory.concentrator import ConcentrateJob
from memory.entity import EntityProfile
from memory.long_term import LongTermMemory
from memory.manager import MemoryManager
from memory.relationship import RelationshipGraph
from ui.sender import DelaySendScheduler

logger = logging.getLogger(__name__)


def build_app(config_path: str = "conf/bot.yaml") -> tuple:
    """Assemble all components and return (main_loop, shutdown_manager, incoming_queue)."""
    config = ConfigLoader.load(config_path)
    setup_logger("chatter", log_dir="logs")

    # Infrastructure
    llm = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    raw_log = RawMessageLog("data/raw_messages.db")
    action_log = ActionLog("data/action_log.db")
    long_term = LongTermMemory("data/long_term.db")
    relationship = RelationshipGraph("data/relationship.db")
    entity = EntityProfile("data/entity.db")

    # Memory
    memory = MemoryManager(short_term_max=config.memory.short_term_max)

    # State
    activity_curve = ActivityCurve(config.activity)
    state = BotState(config, activity_curve)
    state_events = StateEventQueue()

    # Message ingestion
    incoming_queue: queue.Queue = queue.Queue()
    ingestor = MessageIngestor(incoming_queue, memory, raw_log)

    # Decision
    passive_judge = PassiveReplyJudge(config)
    active_gate = ActiveSpeakGate(config, state)
    engine = DecisionEngine(passive_judge, active_gate, memory, llm)

    # Generation
    formatter = ResponseFormatter(config)
    content_gen = ContentGenerator(llm, formatter)
    degraded_policy = DegradedReplyPolicy(config)

    # Concentration
    concentrator = ConcentrateJob(llm, long_term, config)

    # Brake & Send
    brake = EmergencyBrake(config)
    adapter = BotAdapter(bot=None)
    sender = DelaySendScheduler(adapter, action_log, brake, state_events, config)

    # Orchestrator
    orchestrator = Orchestrator(
        state=state,
        engine=engine,
        content_gen=content_gen,
        brake=brake,
        sender=sender,
        action_log=action_log,
        memory=memory,
        llm=llm,
        degraded_policy=degraded_policy,
        config=config,
        state_events=state_events,
        ingestor=ingestor,
        concentrator=concentrator,
    )

    # Main loop
    main_loop = MainLoop(orchestrator, state, config)

    # Shutdown
    shutdown_mgr = ShutdownManager(
        main_loop=main_loop,
        sender=sender,
        state=state,
        action_log=action_log,
        raw_log=raw_log,
        long_term=long_term,
        relationship=relationship,
        entity=entity,
        llm=llm,
    )

    return main_loop, shutdown_mgr, incoming_queue


if __name__ == "__main__":
    main_loop, shutdown_mgr, _ = build_app()
    shutdown_mgr.install_signal_handlers()
    main_loop.start()
    try:
        # Block until interrupted
        shutdown_mgr.main_loop._thread.join()
    except KeyboardInterrupt:
        shutdown_mgr.shutdown(drain_pending=True)
        sys.exit(0)
