"""Logging configuration for VoiceIME."""

from __future__ import annotations

import logging
from pathlib import Path

from voiceime.utils.paths import log_dir


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with console + file handlers."""
    log_dir().mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("voiceime")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if root.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.FileHandler(
        log_dir() / "voiceime.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
