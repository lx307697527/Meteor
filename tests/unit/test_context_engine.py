"""Unit tests for voiceime.context.engine — ContextEngine rule matching."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import ContextOverrides, ProcessContext


@pytest.fixture
def rules_file(tmp_path):
    """Temporary context_rules.json path."""
    return tmp_path / "context_rules.json"


@pytest.fixture
def config():
    """Mock config provider."""
    cfg = MagicMock()
    cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "context.enabled": True,
        "context.cache_ttl_ms": 200,
    }.get(k, d))
    return cfg


class TestContextEngineGetContext:
    def test_should_return_process_context_from_window(self, config):
        from voiceime.context.engine import ContextEngine
        from voiceime.context.window import WindowInfo

        with patch("voiceime.context.engine.get_foreground_window",
                   return_value=WindowInfo("Code.exe", "test.py")):
            engine = ContextEngine(config=config)
            ctx = engine.get_context()
            assert ctx.app_name == "Code.exe"
            assert ctx.app_title == "test.py"

    def test_should_return_none_values_when_no_window(self, config):
        from voiceime.context.engine import ContextEngine
        from voiceime.context.window import WindowInfo

        with patch("voiceime.context.engine.get_foreground_window",
                   return_value=WindowInfo("", "")):
            engine = ContextEngine(config=config)
            ctx = engine.get_context()
            assert ctx.app_name is None
            assert ctx.app_title is None

    def test_should_return_empty_when_disabled(self, config):
        from voiceime.context.engine import ContextEngine

        config.get = MagicMock(return_value=False)
        with patch("voiceime.context.engine.get_foreground_window",
                   return_value=("Code.exe", "test.py")):
            engine = ContextEngine(config=config)
            ctx = engine.get_context()
            assert ctx.app_name is None
            assert ctx.app_title is None


class TestContextEngineMatchRules:
    def test_should_match_vscode_rule(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="Code.exe", app_title="main.rs — Meteor")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.quick_mode is False
        assert overrides.polish_mode == "manual"
        assert overrides.system_prompt is not None

    def test_should_match_wechat_rule(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="WeChat.exe", app_title="聊天")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.quick_mode is True
        assert overrides.polish_mode == "off"

    def test_should_match_word_rule(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="WINWORD.EXE", app_title="报告.docx - Word")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.polish_mode == "auto"
        assert overrides.system_prompt is not None
        assert "商务" in overrides.system_prompt

    def test_should_match_wps_rule(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="wps.exe", app_title="文档")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.polish_mode == "auto"

    def test_should_match_idea_rule(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="idea64.exe", app_title="MyProject")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.quick_mode is False
        assert overrides.polish_mode == "manual"

    def test_should_return_none_for_unknown_app(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="unknown.exe", app_title="mystery")
        overrides = engine.match_rules(ctx)
        assert overrides is None

    def test_should_return_none_when_disabled(self, config):
        from voiceime.context.engine import ContextEngine

        config.get = MagicMock(return_value=False)
        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="Code.exe", app_title="test")
        overrides = engine.match_rules(ctx)
        assert overrides is None

    def test_should_return_none_when_no_app_or_title(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name=None, app_title=None)
        overrides = engine.match_rules(ctx)
        assert overrides is None

    def test_should_skip_disabled_rules(self, config, rules_file):
        rules_file.write_text(json.dumps([{
            "name": "DisabledVSCode", "app_name_pattern": "code.exe",
            "title_pattern": "", "enabled": False,
            "overrides": {"quick_mode": True}
        }]), encoding="utf-8")

        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config, rules_path=rules_file)
        ctx = ProcessContext(app_name="Code.exe", app_title="test")
        overrides = engine.match_rules(ctx)
        assert overrides is None

    def test_should_match_by_title_substring(self, config, rules_file):
        rules_file.write_text(json.dumps([{
            "name": "ChatTitle", "app_name_pattern": "",
            "title_pattern": "chat", "enabled": True,
            "overrides": {"quick_mode": True}
        }]), encoding="utf-8")

        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config, rules_path=rules_file)
        ctx = ProcessContext(app_name="any.exe", app_title="Discord Chat Room")
        overrides = engine.match_rules(ctx)
        assert overrides is not None
        assert overrides.quick_mode is True

    def test_should_not_match_when_title_does_not_match(self, config, rules_file):
        rules_file.write_text(json.dumps([{
            "name": "SpecificTitle", "app_name_pattern": "",
            "title_pattern": "specific", "enabled": True,
            "overrides": {}
        }]), encoding="utf-8")

        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config, rules_path=rules_file)
        ctx = ProcessContext(app_name="any.exe", app_title="Something Else")
        overrides = engine.match_rules(ctx)
        assert overrides is None


class TestContextEngineReload:
    def test_should_reload_rules_from_disk(self, config, rules_file):
        rules_file.write_text(json.dumps([]), encoding="utf-8")

        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config, rules_path=rules_file)
        assert len(engine.repo.list_all()) == 0

        rules_file.write_text(json.dumps([{
            "name": "NewRule", "app_name_pattern": "n.exe",
            "title_pattern": "", "enabled": True, "overrides": {}
        }]), encoding="utf-8")

        engine.reload_rules()
        assert len(engine.repo.list_all()) == 1
        assert engine.repo.list_all()[0]["name"] == "NewRule"


class TestContextOverrides:
    def test_should_create_with_all_none_defaults(self):
        ov = ContextOverrides(
            quick_mode=None, polish_mode=None, system_prompt=None,
            punct_normalize=None, t2s_enabled=None, hotword_enabled=None,
        )
        assert ov.quick_mode is None
        assert ov.polish_mode is None
        assert ov.system_prompt is None

    def test_should_store_override_values(self):
        ov = ContextOverrides(
            quick_mode=True, polish_mode="auto", system_prompt="test_prompt",
            punct_normalize=False, t2s_enabled=None, hotword_enabled=None,
        )
        assert ov.quick_mode is True
        assert ov.polish_mode == "auto"
        assert ov.system_prompt == "test_prompt"
        assert ov.punct_normalize is False


class TestRuleMatching:
    def test_should_match_suffix_case_insensitive(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="CODE.EXE", app_title="test")
        overrides = engine.match_rules(ctx)
        assert overrides is not None

    def test_should_not_match_partial_suffix(self, config):
        from voiceime.context.engine import ContextEngine

        engine = ContextEngine(config=config)
        ctx = ProcessContext(app_name="notepad.exe", app_title="test")
        overrides = engine.match_rules(ctx)
        # "notepad.exe" does not end with "code.exe" or any known pattern = no match
        assert overrides is None
