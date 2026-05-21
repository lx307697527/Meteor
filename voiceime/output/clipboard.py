"""ClipboardGuard — backup, write, paste, restore."""

from __future__ import annotations

import logging
import time

import pyautogui
import pyperclip

logger = logging.getLogger("voiceime.output.clipboard")

_DEFAULT_RESTORE_DELAY_MS = 50


class ClipboardGuard:
    """Protects clipboard content during text output."""

    def __init__(self, restore_delay_ms: int = _DEFAULT_RESTORE_DELAY_MS) -> None:
        self._delay = restore_delay_ms / 1000.0

    def backup(self) -> str | None:
        """Save current clipboard content. Returns None if clipboard is empty."""
        try:
            return pyperclip.paste()
        except Exception as exc:
            logger.warning("Failed to backup clipboard: %s", exc)
            return None

    def write_and_paste(self, text: str) -> bool:
        """Write text to clipboard and simulate Ctrl+V."""
        try:
            pyperclip.copy(text)
            time.sleep(0.05)  # Brief pause for clipboard to update
            pyautogui.hotkey("ctrl", "v")
            return True
        except Exception as exc:
            logger.error("Clipboard write+paste failed: %s", exc)
            return False

    def restore(self, backup: str | None) -> bool:
        """Restore original clipboard content."""
        if backup is None:
            return True
        try:
            time.sleep(self._delay)
            pyperclip.copy(backup)
            return True
        except Exception as exc:
            logger.warning("Failed to restore clipboard: %s", exc)
            return False
