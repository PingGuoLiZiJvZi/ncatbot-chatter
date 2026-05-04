from __future__ import annotations

import os
from pathlib import Path

import yaml

from conf.schema import BotConfig


class ConfigLoader:
    @staticmethod
    def load(path: str | Path | None = None) -> BotConfig:
        if path is None:
            path = os.environ.get("BOT_CONFIG_PATH", "conf/bot.yaml")
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"Config file is empty: {path}")
        return BotConfig(**data)
