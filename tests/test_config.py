import os
import pytest
from conf.schema import BotConfig, EmotionConfig, MemoryConfig, MemoryThresholds, SendConfig, ActivityConfig, LoopConfig, LLMConfig
from conf.loader import ConfigLoader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestBotConfig:
    def test_default_values(self):
        cfg = BotConfig(bot_uin="123", root_uin="456", api_key="sk-test")
        assert cfg.bot_uin == "123"
        assert cfg.root_uin == "456"
        assert cfg.base_url == "https://api.deepseek.com/anthropic"
        assert cfg.model == "deepseek-v4-pro"
        assert cfg.temperature == 1.3
        assert cfg.max_tokens == 2048

    def test_emotion_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert cfg.emotion.valence_regression == 0.01
        assert cfg.emotion.energy_regen_per_hour == 0.1
        assert cfg.emotion.sleep_regen_multiplier == 3.0

    def test_memory_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert cfg.memory.short_term_max == 20
        assert cfg.memory.pending_threshold == 12
        assert cfg.memory.thresholds.event == 6
        assert cfg.memory.thresholds.fact == 6
        assert cfg.memory.thresholds.impression == 5
        assert cfg.memory.thresholds.plan == 7
        assert cfg.memory.dedup_ttl_days == 7
        assert cfg.memory.archive_expired is True

    def test_send_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert cfg.send.min_interval_same_chat == 120.0
        assert cfg.send.passive_delay_mu == 30.0
        assert cfg.send.active_delay_mu == 120.0

    def test_activity_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert len(cfg.activity.hourly_weights) == 24
        assert cfg.activity.sleep_hours == (0, 7)

    def test_loop_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert cfg.loop.passive_interval == 3.0
        assert cfg.loop.active_interval == 60.0
        assert cfg.loop.concentrate_interval == 300.0

    def test_llm_defaults(self):
        cfg = BotConfig(bot_uin="1", root_uin="2", api_key="k")
        assert cfg.llm.max_consecutive_failures == 5
        assert cfg.llm.health_check_interval == 10


class TestConfigLoader:
    def test_load_template(self):
        template_path = os.path.join(PROJECT_ROOT, "conf", "bot.yaml.template")
        cfg = ConfigLoader.load(template_path)
        assert isinstance(cfg, BotConfig)

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load("/nonexistent/path.yaml")

    def test_hourly_weights_validation(self):
        with pytest.raises(Exception):
            ActivityConfig(hourly_weights=[0.0] * 23)  # too few

    def test_memory_thresholds_validation(self):
        with pytest.raises(Exception):
            MemoryThresholds(event=0)  # below ge=1

    def test_memory_thresholds_upper_bound(self):
        with pytest.raises(Exception):
            MemoryThresholds(event=11)  # above le=10
