import pytest
from conf.schema import BotConfig
from core.degraded_policy import DegradedReplyPolicy
from core.schemas import ActionPlan, ActionType, Priority


def _make_plan(action_id: str = "a-001") -> ActionPlan:
    return ActionPlan(
        action_id=action_id, action_type=ActionType.PASSIVE_REPLY,
        priority=Priority.P0, chat_id="100", chat_type="group",
        trigger_message="hello", trigger_type="passive_tick", reason="test",
    )


class TestDegradedReplyPolicy:
    def test_generate_returns_template(self):
        cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
        policy = DegradedReplyPolicy(cfg)
        results = policy.generate([_make_plan()])
        # May be 0 or 1 due to silence probability, run multiple times
        all_results = []
        for _ in range(20):
            all_results.extend(policy.generate([_make_plan()]))
        assert len(all_results) > 0
        for r in all_results:
            assert r.content in policy.templates

    def test_generate_with_custom_templates(self):
        cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
        policy = DegradedReplyPolicy(cfg, templates=["custom reply"])
        results = policy.generate([_make_plan()])
        # May be silenced, try again
        for _ in range(10):
            results = policy.generate([_make_plan()])
            if results:
                assert results[0].content == "custom reply"
                break

    def test_silence_probability(self):
        cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
        policy = DegradedReplyPolicy(cfg)
        policy.silence_probability = 1.0  # always silent
        results = policy.generate([_make_plan()])
        assert len(results) == 0

    def test_generate_multiple_plans(self):
        cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
        policy = DegradedReplyPolicy(cfg)
        policy.silence_probability = 0.0  # never silent
        plans = [_make_plan(f"a-{i}") for i in range(5)]
        results = policy.generate(plans)
        assert len(results) == 5
