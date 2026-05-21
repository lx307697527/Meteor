"""ContextRuleRepo — context_rules.json CRUD for context-aware behavior overrides."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from voiceime.utils.paths import context_rules_path

logger = logging.getLogger("voiceime.context.rules")

_MAX_RULES = 200


class ContextRuleRepo:
    """JSON-backed context rule repository."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or context_rules_path()
        self._rules: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._rules = self._default_rules()
            self._save()
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                self._rules = [
                    r for r in data
                    if isinstance(r, dict) and "name" in r and "app_name_pattern" in r
                ]
            else:
                logger.warning("context_rules.json is not a list, using defaults")
                self._rules = self._default_rules()
                self._save()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("context_rules.json corrupted, resetting: %s", exc)
            bak = self._path.with_suffix(".json.bak")
            try:
                self._path.replace(bak)
            except OSError:
                pass
            self._rules = self._default_rules()
            self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._rules, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._path)

    def _default_rules(self) -> list[dict]:
        return [
            {
                "name": "VSCode 代码注释",
                "app_name_pattern": "code.exe",
                "title_pattern": "",
                "enabled": True,
                "overrides": {
                    "quick_mode": False,
                    "polish_mode": "manual",
                    "system_prompt": "code_comment",
                },
            },
            {
                "name": "IDEA 代码注释",
                "app_name_pattern": "idea64.exe",
                "title_pattern": "",
                "enabled": True,
                "overrides": {
                    "quick_mode": False,
                    "polish_mode": "manual",
                    "system_prompt": "code_comment",
                },
            },
            {
                "name": "微信快速上屏",
                "app_name_pattern": "wechat.exe",
                "title_pattern": "",
                "enabled": True,
                "overrides": {
                    "quick_mode": True,
                    "polish_mode": "off",
                },
            },
            {
                "name": "Word 商务书面",
                "app_name_pattern": "winword.exe",
                "title_pattern": "",
                "enabled": True,
                "overrides": {
                    "polish_mode": "auto",
                    "system_prompt": "business",
                },
            },
            {
                "name": "WPS 商务书面",
                "app_name_pattern": "wps.exe",
                "title_pattern": "",
                "enabled": True,
                "overrides": {
                    "polish_mode": "auto",
                    "system_prompt": "business",
                },
            },
        ]

    # ── CRUD ──────────────────────────────────────────

    def add(self, rule: dict) -> None:
        if len(self._rules) >= _MAX_RULES:
            raise ValueError(f"Max rules ({_MAX_RULES}) reached")
        self._rules.append(rule)
        self._save()

    def update(self, index: int, rule: dict) -> None:
        if not (0 <= index < len(self._rules)):
            raise IndexError(f"Index {index} out of range")
        self._rules[index] = rule
        self._save()

    def delete(self, index: int) -> bool:
        if not (0 <= index < len(self._rules)):
            return False
        del self._rules[index]
        self._save()
        return True

    def list_all(self) -> list[dict]:
        return list(self._rules)

    def set_all(self, rules: list[dict]) -> None:
        self._rules = rules
        self._save()
