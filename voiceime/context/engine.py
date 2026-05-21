"""ContextEngine — detect foreground window and match context-aware rules."""

from __future__ import annotations

import logging
from pathlib import Path

from voiceime.context.rules import ContextRuleRepo
from voiceime.context.window import WindowInfo, get_foreground_window, set_cache_ttl
from voiceime.llm.prompts import BUSINESS_PROMPT, CODE_COMMENT_PROMPT, DEFAULT_SYSTEM_PROMPT
from voiceime.protocols import ContextOverrides, ProcessContext

logger = logging.getLogger("voiceime.context.engine")

# Map from short prompt keys in rule JSON to actual prompt strings
_PROMPT_MAP = {
    "code_comment": CODE_COMMENT_PROMPT,
    "business": BUSINESS_PROMPT,
    "default": DEFAULT_SYSTEM_PROMPT,
}


class ContextEngine:
    """Detect foreground window context and match behavior override rules."""

    def __init__(self, config=None, rules_path: Path | None = None) -> None:
        self._config = config
        self._repo = ContextRuleRepo(rules_path)
        if config:
            ttl_ms = config.get("context.cache_ttl_ms", 200)
            set_cache_ttl(ttl_ms)
        self._enabled = config.get("context.enabled", True) if config else True

    def get_context(self) -> ProcessContext:
        """Detect foreground window and return ProcessContext."""
        if not self._enabled:
            return ProcessContext(app_name=None, app_title=None)
        info = get_foreground_window()
        return ProcessContext(
            app_name=info.app_name or None,
            app_title=info.app_title or None,
        )

    def match_rules(self, context: ProcessContext) -> ContextOverrides | None:
        """Match context against loaded rules, return first match's overrides."""
        if not self._enabled:
            return None
        if not context.app_name and not context.app_title:
            return None

        for rule in self._repo.list_all():
            if not rule.get("enabled", True):
                continue
            if self._rule_matches(rule, context):
                return self._build_overrides(rule)

        return None

    def reload_rules(self) -> None:
        """Re-read rules from disk."""
        self._repo = ContextRuleRepo(self._repo._path)
        logger.info("Context rules reloaded (%d rules)", len(self._repo.list_all()))

    @property
    def repo(self) -> ContextRuleRepo:
        return self._repo

    @staticmethod
    def _rule_matches(rule: dict, context: ProcessContext) -> bool:
        app_pattern = rule.get("app_name_pattern", "").lower()
        title_pattern = rule.get("title_pattern", "")

        # app_name matching: suffix match or contains match
        app_match = False
        if app_pattern:
            if not context.app_name:
                return False
            app_lower = context.app_name.lower()
            if app_lower.endswith(app_pattern):
                app_match = True
            elif app_pattern.lstrip("*") in app_lower:
                app_match = True
        else:
            # Empty app pattern = match any app
            app_match = True

        # title matching: substring match (empty = match all)
        title_match = True
        if title_pattern and context.app_title:
            title_match = title_pattern.lower() in context.app_title.lower()
        elif title_pattern and not context.app_title:
            title_match = False

        return app_match and title_match

    @staticmethod
    def _build_overrides(rule: dict) -> ContextOverrides:
        ov = rule.get("overrides", {})
        prompt_key = ov.get("system_prompt")
        system_prompt = _PROMPT_MAP.get(prompt_key, prompt_key) if prompt_key else None
        return ContextOverrides(
            quick_mode=ov.get("quick_mode"),
            polish_mode=ov.get("polish_mode"),
            system_prompt=system_prompt,
            punct_normalize=ov.get("punct_normalize"),
            t2s_enabled=ov.get("t2s_enabled"),
            hotword_enabled=ov.get("hotword_enabled"),
        )
