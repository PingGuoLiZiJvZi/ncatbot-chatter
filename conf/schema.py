from __future__ import annotations

from pydantic import BaseModel, Field


class EmotionConfig(BaseModel):
    valence_regression: float = Field(default=0.01, ge=0.0, le=1.0)
    energy_regen_per_hour: float = Field(default=0.1, ge=0.0, le=1.0)
    sleep_regen_multiplier: float = Field(default=3.0, ge=1.0, le=10.0)
    valence_step: float = Field(default=0.1, ge=0.0, le=1.0)
    energy_step: float = Field(default=0.05, ge=0.0, le=1.0)
    interest_step: float = Field(default=0.1, ge=0.0, le=1.0)


class MemoryThresholds(BaseModel):
    event: int = Field(default=6, ge=1, le=10)
    fact: int = Field(default=6, ge=1, le=10)
    impression: int = Field(default=5, ge=1, le=10)
    plan: int = Field(default=7, ge=1, le=10)


class MemoryConfig(BaseModel):
    short_term_max: int = Field(default=20, ge=5, le=100)
    pending_threshold: int = Field(default=12, ge=5, le=50)
    thresholds: MemoryThresholds = MemoryThresholds()
    dedup_ttl_days: int = Field(default=7, ge=1, le=30)
    archive_expired: bool = True


class SendConfig(BaseModel):
    min_interval_same_chat: float = Field(default=120.0, ge=0.0)
    passive_delay_mu: float = Field(default=30.0, ge=0.0)
    passive_delay_sigma: float = Field(default=15.0, ge=0.0)
    passive_delay_min: float = Field(default=5.0, ge=0.0)
    passive_delay_max: float = Field(default=120.0, ge=0.0)
    active_delay_mu: float = Field(default=120.0, ge=0.0)
    active_delay_sigma: float = Field(default=60.0, ge=0.0)
    active_delay_min: float = Field(default=30.0, ge=0.0)
    active_delay_max: float = Field(default=300.0, ge=0.0)


class ActivityConfig(BaseModel):
    hourly_weights: list[float] = Field(
        default_factory=lambda: [0.0] * 7 + [0.1, 0.3, 0.5, 0.7, 0.8, 0.6, 0.7, 0.8, 0.9, 0.9, 0.8, 0.7, 0.8, 0.9, 0.8, 0.5, 0.2],
        min_length=24,
        max_length=24,
    )
    sleep_hours: tuple[int, int] = (0, 7)


class LoopConfig(BaseModel):
    passive_interval: float = Field(default=3.0, ge=1.0)
    active_interval: float = Field(default=60.0, ge=1.0)
    concentrate_interval: float = Field(default=300.0, ge=1.0)


class LLMConfig(BaseModel):
    max_consecutive_failures: int = Field(default=5, ge=1, le=20)
    health_check_interval: int = Field(default=10, ge=1, le=100)


class BotConfig(BaseModel):
    bot_uin: str
    root_uin: str
    api_key: str
    base_url: str = "https://api.deepseek.com/anthropic"
    model: str = "deepseek-v4-pro"
    temperature: float = Field(default=1.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)
    emotion: EmotionConfig = EmotionConfig()
    memory: MemoryConfig = MemoryConfig()
    send: SendConfig = SendConfig()
    activity: ActivityConfig = ActivityConfig()
    loop: LoopConfig = LoopConfig()
    llm: LLMConfig = LLMConfig()
