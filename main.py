from __future__ import annotations

import logging
import queue
import sys

from ncatbot.core import BotClient

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


def build_app(bot: BotClient, config_path: str = "conf/bot.yaml") -> tuple:
    """Assemble all components and return (main_loop, shutdown_manager).

    Registers ncatbot event handlers on *bot* that feed messages into the
    internal pipeline.
    """
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
    adapter = BotAdapter(bot=bot)
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

    # ── Register ncatbot event handlers ──────────────────────────────
    bot_uin = config.bot_uin

    @bot.group_event()
    async def on_group_message(msg):
        raw = getattr(msg, "raw_message", "") or ""
        logger.info("Group message from %s in %s: %s", msg.user_id, msg.group_id, raw[:50])
        incoming_queue.put(msg)
        # Wake up MainLoop immediately for @ mentions
        if f"@{bot_uin}" in raw or f"[CQ:at,qq={bot_uin}]" in raw:
            main_loop.wake_up()

    @bot.private_event()
    async def on_private_message(msg):
        logger.info("Private message from %s: %s", msg.user_id, (getattr(msg, "raw_message", "") or "")[:50])
        incoming_queue.put(msg)
        # Private messages are always P0 — wake up immediately
        main_loop.wake_up()

    return main_loop, shutdown_mgr, sender


if __name__ == "__main__":
    config = ConfigLoader.load("conf/bot.yaml")

    bot = BotClient()
    main_loop, shutdown_mgr, sender = build_app(bot)

    logger.info("Starting MainLoop and sender...")
    sender.start()
    main_loop.start()
    logger.info("MainLoop running. Connecting to QQ (bot_uin=%s)...", config.bot_uin)

    try:
        # bot.run() blocks: launches napcat, connects websocket, dispatches events.
        # ncatbot catches KeyboardInterrupt internally and calls bot_exit().
        bot.run(bt_uin=config.bot_uin, root=config.root_uin)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    finally:
        logger.info("Shutting down...")
        shutdown_mgr.shutdown(drain_pending=True)
