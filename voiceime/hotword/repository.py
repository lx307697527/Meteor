"""HotwordRepo — hotwords.json CRUD with case-insensitive matching and CSV support."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from voiceime.protocols import HotwordProvider
from voiceime.utils.paths import hotwords_path

logger = logging.getLogger("voiceime.hotword.repository")

_MAX_ENTRIES = 10000
_LEVELS = 50


class HotwordRepo:
    """JSON-backed hotword repository with case-insensitive find()."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or hotwords_path()
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._entries = []
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                self._entries = [
                    e for e in data
                    if isinstance(e, dict) and "trigger" in e and "replace" in e
                ]
            else:
                logger.warning("hotwords.json is not a list, resetting")
                self._entries = []
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("hotwords.json corrupted, resetting: %s", exc)
            bak = self._path.with_suffix(".json.bak")
            try:
                self._path.replace(bak)
            except OSError:
                pass
            self._entries = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._path)

    # ── CRUD ──────────────────────────────────────────────

    def add(self, trigger: str, replace: str, case_sensitive: bool = False) -> None:
        if len(self._entries) >= _MAX_ENTRIES:
            raise ValueError(f"Max entries ({_MAX_ENTRIES}) reached")
        self._entries.append({
            "trigger": trigger,
            "replace": replace,
            "case_sensitive": case_sensitive,
        })
        self._save()

    def update(self, index: int, trigger: str, replace: str,
               case_sensitive: bool = False) -> None:
        if not (0 <= index < len(self._entries)):
            raise IndexError(f"Index {index} out of range")
        self._entries[index] = {
            "trigger": trigger,
            "replace": replace,
            "case_sensitive": case_sensitive,
        }
        self._save()

    def delete(self, index: int) -> bool:
        if not (0 <= index < len(self._entries)):
            return False
        del self._entries[index]
        self._save()
        return True

    # ── Query ─────────────────────────────────────────────

    def find(self, trigger: str) -> str | None:
        for entry in self._entries:
            if entry.get("case_sensitive"):
                if entry["trigger"] == trigger:
                    return entry["replace"]
            else:
                if entry["trigger"].lower() == trigger.lower():
                    return entry["replace"]
        return None

    def list_all(self) -> list[dict]:
        return list(self._entries)

    # ── CSV ───────────────────────────────────────────────

    def import_csv(self, csv_path: Path) -> int:
        imported = 0
        existing_triggers = {
            e["trigger"].lower() for e in self._entries
            if not e.get("case_sensitive")
        }
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                trigger, replace = row[0].strip(), row[1].strip()
                if not trigger or not replace:
                    continue
                if trigger.lower() in existing_triggers:
                    continue
                self._entries.append({
                    "trigger": trigger,
                    "replace": replace,
                    "case_sensitive": False,
                })
                existing_triggers.add(trigger.lower())
                imported += 1
        if imported > 0:
            self._save()
        return imported

    def export_csv(self, csv_path: Path) -> None:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["trigger", "replace"])
            for entry in self._entries:
                writer.writerow([entry["trigger"], entry["replace"]])
