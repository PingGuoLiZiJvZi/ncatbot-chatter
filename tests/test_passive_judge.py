from datetime import datetime
import pytest
from conf.schema import BotConfig
from core.passive_judge import PassiveReplyJudge
from core.schemas import Priority, ActionType
from memory.schemas import Message
from memory.short_term import ShortTermMemory


def _make_config() -> BotConfig:
    return BotConfig(bot_uin="12345", root_uin="99999", api_key="sk-test")


def _make_msg(msg_id: str, content: str, chat_id: str = "100", chat_type: str = "group", user_id: str = "200") -> Message:
    return Message(
        message_id=msg_id, chat_type=chat_type, chat_id=chat_id,
        user_id=user_id, user_nickname="test", group_nickname="test",
        content=content, timestamp=datetime.now(),
    )


class TestPassiveReplyJudge:
    def test_at_bot_generates_p0(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        chat.add_incoming(_make_msg("m1", "@12345 hello"))
        plans = judge.evaluate([chat])
        assert len(plans) == 1
        assert plans[0].priority == Priority.P0

    def test_at_bot_cq_code(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        chat.add_incoming(_make_msg("m1", "[CQ:at,qq=12345] hi"))
        plans = judge.evaluate([chat])
        assert len(plans) == 1
        assert plans[0].priority == Priority.P0

    def test_private_message_generates_p0(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("300")
        chat.add_incoming(_make_msg("m1", "hello", chat_id="300", chat_type="private"))
        plans = judge.evaluate([chat])
        assert len(plans) == 1
        assert plans[0].priority == Priority.P0

    def test_mentioned_generates_p1(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        chat.add_incoming(_make_msg("m1", "12345 is cool"))
        plans = judge.evaluate([chat])
        assert len(plans) == 1
        assert plans[0].priority == Priority.P1

    def test_normal_group_no_plan(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        chat.add_incoming(_make_msg("m1", "just a normal message"))
        plans = judge.evaluate([chat])
        assert len(plans) == 0

    def test_empty_unread(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        plans = judge.evaluate([chat])
        assert len(plans) == 0

    def test_multiple_at_messages(self):
        judge = PassiveReplyJudge(_make_config())
        chat = ShortTermMemory("100")
        chat.add_incoming(_make_msg("m1", "@12345 first"))
        chat.add_incoming(_make_msg("m2", "@12345 second"))
        plans = judge.evaluate([chat])
        assert len(plans) == 2
