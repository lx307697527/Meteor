"""ConfigManager unit tests — F09: config read/write, corruption recovery."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


@contextmanager
def _patched(tmp_data_dir: Path):
    config_file = tmp_data_dir / "config.json"
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    with (
        patch("voiceime.config.manager.config_path", return_value=config_file),
        patch("voiceime.config.manager.data_dir", return_value=tmp_data_dir),
    ):
        yield config_file


class TestConfigManager:
    """ConfigManager — dot-path access, persistence, corruption recovery."""

    def test_should_return_default_when_config_file_missing(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir) as cfg_file:
            # No config file exists yet
            mgr = ConfigManager()
            # Auto-created with defaults
            assert cfg_file.exists()
            assert mgr.get("asr.model") == "large-v3-turbo"

    def test_should_return_correct_value_when_reading_existing_key(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            assert mgr.get("asr.model") == "large-v3-turbo"
            assert mgr.get("asr.quantization") == "int8"
            assert mgr.get("hotkey") == "caps_lock"

    def test_should_return_default_when_key_not_found(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            assert mgr.get("nonexistent.key", default="fallback") == "fallback"

    def test_should_persist_value_when_setting_key(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            mgr.set("asr.vad_filter", False)
            mgr.reload()
            assert mgr.get("asr.vad_filter") is False

    def test_should_recover_default_when_json_corrupted(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = tmp_data_dir / "config.json"
        cfg_file.write_text("{invalid json", encoding="utf-8")

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            # Should recover to defaults, not crash
            assert mgr.get("asr.model") is not None

    def test_should_create_nested_key_on_set(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            mgr.set("custom.deep.key", 42)
            assert mgr.get("custom.deep.key") == 42

    def test_should_return_data_dir_path(self, tmp_data_dir):
        from voiceime.config.manager import ConfigManager

        with _patched(tmp_data_dir):
            mgr = ConfigManager()
            assert mgr.data_dir == tmp_data_dir
