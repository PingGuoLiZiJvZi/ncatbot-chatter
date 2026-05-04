"""Simulation script: injects synthetic messages and observes orchestrator output.

Does NOT depend on ncatbot or a real QQ account.
Usage: conda run -n bot python scripts/run_sim.py
"""
from __future__ import annotations

import logging
import queue
import time
from datetime import datetime
from unittest.mock import MagicMock

from conf.schema import BotConfig
from core.activity_curve import ActivityCurve
from core.degraded_policy import DegradedReplyPolicy
from core.decision import DecisionEngine
from core.emergency_brake import EmergencyBrake
from core.main_loop import MainLoop
from core.orchestrator import Orchestrator
from core.passive_judge import PassiveReplyJudge
from core.active_gate import ActiveSpeakGate
from core.state import BotState, StateEventQueue
from generation.content_gen import ContentGenerator
from generation.formatter import ResponseFormatter
from infra.action_log import ActionLog
from infra.bot_adapter import BotAdapter, SendResult, SendStatus
from infra.llm_client import LLMClient
from infra.message_ingestor import MessageIngestor
from infra.raw_message_log import RawMessageLog
from infra.logger import setup_logger
from memory.concentrator import ConcentrateJob
from memory.entity import EntityProfile
from memory.long_term import LongTermMemory
from memory.manager import MemoryManager
from memory.relationship import RelationshipGraph
from memory.schemas import Message
from ui.sender import DelaySendScheduler

logger = logging.getLogger("sim")


def make_sim_config() -> BotConfig:
    cfg = BotConfig(bot_uin="10000", root_uin="99999", api_key="sk-sim")
    cfg.send.passive_delay_min = 0.1
    cfg.send.passive_delay_max = 0.5
    cfg.send.active_delay_min = 0.1
    cfg.send.active_delay_max = 0.5
    cfg.send.min_interval_same_chat = 1.0
    cfg.loop.passive_interval = 0.5
    cfg.loop.active_interval = 2.0
    cfg.loop.concentrate_interval = 10.0
    cfg.memory.pending_threshold = 3
    return cfg


def make_mock_adapter() -> MagicMock:
    adapter = MagicMock(spec=BotAdapter)
    adapter.send_group_msg.side_effect = lambda gid, content, **kw: SendResult(
        action_id=kw.get("action_id", ""), status=SendStatus.SENT, latency_ms=10,
    )
    adapter.send_private_msg.side_effect = lambda uid, content, **kw: SendResult(
        action_id=kw.get("action_id", ""), status=SendStatus.SENT, latency_ms=10,
    )
    return adapter


def make_mock_llm() -> MagicMock:
    llm = MagicMock(spec=LLMClient)
    llm.chat_text.return_value = '[{"content": "模拟回复~", "mention_user_id": null, "reply_to_message_id": null}]'
    llm.health_check.return_value = True
    return llm


def inject_at_message(q: queue.Queue, group_id: str = "100", user_id: str = "200"):
    event = MagicMock()
    event.__class__.__name__ = "GroupMessage"
    event.message_id = f"msg_{int(time.time() * 1000)}"
    event.group_id = group_id
    event.user_id = user_id
    event.message = [{"type": "text", "data": {"text": "@bot 你好呀"}}]
    event.sender = {"nickname": "Alice", "card": "Alice"}
    q.put(event)


def inject_private_message(q: queue.Queue, user_id: str = "300"):
    event = MagicMock()
    event.__class__.__name__ = "PrivateMessage"
    event.message_id = f"msg_{int(time.time() * 1000)}"
    event.user_id = user_id
    event.message = [{"type": "text", "data": {"text": "你好"}}]
    event.sender = {"nickname": "Bob"}
    q.put(event)


def inject_group_message(q: queue.Queue, group_id: str = "100", user_id: str = "400", text: str = "今天天气不错"):
    event = MagicMock()
    event.__class__.__name__ = "GroupMessage"
    event.message_id = f"msg_{int(time.time() * 1000)}"
    event.group_id = group_id
    event.user_id = user_id
    event.message = [{"type": "text", "data": {"text": text}}]
    event.sender = {"nickname": "Charlie", "card": "Charlie"}
    q.put(event)


def main():
    setup_logger("sim", log_dir="logs")
    cfg = make_sim_config()

    # Infrastructure
    llm = make_mock_llm()
    raw_log = RawMessageLog("data/sim_raw.db")
    action_log = ActionLog("data/sim_action.db")
    long_term = LongTermMemory("data/sim_longterm.db")
    relationship = RelationshipGraph("data/sim_rel.db")
    entity = EntityProfile("data/sim_entity.db")

    memory = MemoryManager(short_term_max=cfg.memory.short_term_max)
    activity_curve = ActivityCurve(cfg.activity)
    state = BotState(cfg, activity_curve)
    state_events = StateEventQueue()

    incoming_queue: queue.Queue = queue.Queue()
    ingestor = MessageIngestor(incoming_queue, memory, raw_log)

    passive_judge = PassiveReplyJudge(cfg)
    active_gate = ActiveSpeakGate(cfg, state)
    engine = DecisionEngine(passive_judge, active_gate, memory, llm)

    formatter = ResponseFormatter(cfg)
    content_gen = ContentGenerator(llm, formatter)
    degraded_policy = DegradedReplyPolicy(cfg)
    concentrator = ConcentrateJob(llm, long_term, cfg)

    brake = EmergencyBrake(cfg)
    adapter = make_mock_adapter()
    sender = DelaySendScheduler(adapter, action_log, brake, state_events, cfg)

    orchestrator = Orchestrator(
        state=state, engine=engine, content_gen=content_gen, brake=brake,
        sender=sender, action_log=action_log, memory=memory, llm=llm,
        degraded_policy=degraded_policy, config=cfg, state_events=state_events,
        ingestor=ingestor, concentrator=concentrator,
    )

    main_loop = MainLoop(orchestrator, state, cfg)
    sender.start()
    main_loop.start()

    # Simulation
    logger.info("=== Simulation started ===")

    # Inject messages
    inject_at_message(incoming_queue)
    inject_private_message(incoming_queue)
    for i in range(3):
        inject_group_message(incoming_queue, text=f"消息 {i}")

    logger.info("Injected 5 messages, waiting for processing...")
    time.sleep(3)

    # Check results
    logger.info("=== Results ===")
    logger.info("Adapter send_group_msg calls: %d", adapter.send_group_msg.call_count)
    logger.info("Adapter send_private_msg calls: %d", adapter.send_private_msg.call_count)
    logger.info("State mode: %s", state.mode.value)
    logger.info("Action log status for first action: check data/sim_action.db")

    # Shutdown
    sender.stop(drain=True)
    main_loop.stop()
    action_log.close()
    raw_log.close()
    long_term.close()
    relationship.close()
    entity.close()
    llm.close()

    logger.info("=== Simulation complete ===")


if __name__ == "__main__":
    main()
