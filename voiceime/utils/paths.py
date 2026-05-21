"""APPDATA path management for VoiceIME."""

from __future__ import annotations

import os
from pathlib import Path

_APP_NAME = "VoiceIME"


def data_dir() -> Path:
    """Return %APPDATA%\\VoiceIME\\ path."""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    return Path(base) / _APP_NAME


def ensure_dirs() -> None:
    """Create all required subdirectories if they don't exist."""
    root = data_dir()
    subdirs = ["models", "logs"]
    root.mkdir(parents=True, exist_ok=True)
    for d in subdirs:
        (root / d).mkdir(exist_ok=True)


def config_path() -> Path:
    return data_dir() / "config.json"


def history_db_path() -> Path:
    return data_dir() / "history.sqlite"


def hotwords_path() -> Path:
    return data_dir() / "hotwords.json"


def log_dir() -> Path:
    return data_dir() / "logs"
