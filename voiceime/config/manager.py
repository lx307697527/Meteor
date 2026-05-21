"""ConfigManager — config.json read/write with dot-path access."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from voiceime.config.defaults import DEFAULT_CONFIG
from voiceime.utils.paths import config_path, data_dir

logger = logging.getLogger("voiceime.config")


class ConfigCorruptedError(Exception):
    pass


class ConfigManager:
    """Thread-safe config.json manager with corruption recovery."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict = {}
        self._path = config_path()
        self._load()

    def _load(self) -> None:
        """Load config from disk, falling back to defaults on corruption."""
        if not self._path.exists():
            self._data = _deep_copy(DEFAULT_CONFIG)
            self._save()
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            self._data = json.loads(raw)
            # Merge with defaults to pick up new keys
            self._data = _deep_merge(_deep_copy(DEFAULT_CONFIG), self._data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Config corrupted, restoring defaults: %s", exc)
            bak = self._path.with_suffix(".json.bak")
            try:
                self._path.replace(bak)
                logger.info("Corrupted config backed up to %s", bak)
            except OSError:
                pass
            self._data = _deep_copy(DEFAULT_CONFIG)
            self._save()

    def _save(self) -> None:
        """Persist current config to disk (write-then-rename for safety)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._path)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-path, e.g. 'asr.model'."""
        with self._lock:
            keys = key.split(".")
            val = self._data
            for k in keys:
                if isinstance(val, dict) and k in val:
                    val = val[k]
                else:
                    return default
            return val

    def set(self, key: str, value: Any) -> None:
        """Set config value by dot-path and persist immediately."""
        with self._lock:
            keys = key.split(".")
            target = self._data
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
            self._save()

    def reload(self) -> None:
        """Reload config from disk."""
        with self._lock:
            self._load()

    @property
    def data_dir(self) -> Path:
        return data_dir()


def _deep_copy(d: dict) -> dict:
    """Simple deep copy for JSON-compatible dicts."""
    return json.loads(json.dumps(d))


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving keys from both."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
