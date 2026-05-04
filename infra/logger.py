from __future__ import annotations

import logging
import os
from pathlib import Path


def setup_logger(
    name: str = "chatter",
    log_dir: str = "logs",
    level: int = logging.DEBUG,
) -> logging.Logger:
    # Configure the root logger so all module loggers (core.*, infra.*, etc.) inherit handlers
    root = logging.getLogger()
    if root.handlers:
        return root
    root.setLevel(level)

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler: INFO+
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler: DEBUG+
    fh = logging.FileHandler(
        os.path.join(log_dir, "bot.log"), encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Error file handler: ERROR+
    eh = logging.FileHandler(
        os.path.join(log_dir, "error.log"), encoding="utf-8"
    )
    eh.setLevel(logging.ERROR)
    eh.setFormatter(fmt)
    root.addHandler(eh)

    return root
