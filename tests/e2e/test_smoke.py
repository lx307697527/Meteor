"""E2E smoke tests — verify modules import and basic instantiation works."""

from unittest.mock import patch

import pytest


class TestSmokeE2E:
    """Smoke tests — minimal validation that the app doesn't crash on import/init."""

    def test_should_import_all_core_modules(self):
        modules = [
            "voiceime.config.defaults",
            "voiceime.config.manager",
            "voiceime.hotkey.hook",
            "voiceime.hotkey.manager",
            "voiceime.recorder.stream",
            "voiceime.asr.engine",
            "voiceime.output.clipboard",
            "voiceime.output.keyboard",
            "voiceime.output.controller",
            "voiceime.model.downloader",
            "voiceime.model.manager",
            "voiceime.protocols",
        ]
        for mod_name in modules:
            __import__(mod_name)

    def test_should_instantiate_asr_engine(self):
        from voiceime.asr.engine import ASREngine

        engine = ASREngine()
        assert engine.is_loaded is False

    def test_should_instantiate_hotkey_manager(self):
        from voiceime.hotkey.manager import HotkeyManager

        mgr = HotkeyManager(hotkey_name="caps_lock")
        assert mgr.current_hotkey == "caps_lock"

    def test_should_instantiate_output_controller(self):
        from voiceime.output.controller import OutputController

        ctrl = OutputController()
        assert hasattr(ctrl, "output")

    def test_should_instantiate_model_manager(self, tmp_path):
        from voiceime.model.manager import ModelManager

        mgr = ModelManager(tmp_path / "models")
        assert isinstance(mgr.available_models, list)

    def test_should_access_default_config(self):
        from voiceime.config.defaults import DEFAULT_CONFIG

        assert "asr" in DEFAULT_CONFIG
        assert "hotkey" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["asr"]["model"] == "large-v3-turbo"

    def test_should_access_protocol_types(self):
        from voiceime.protocols import (
            ASRResult,
            AudioData,
            HotKeyEvent,
            OutputResult,
        )

        assert ASRResult(text="a", language="zh", inference_ms=0, segments=[]).text == "a"
        assert OutputResult(success=True, method="clipboard", error=None).success is True
