"""Keyboard output — character-by-character fallback."""

from __future__ import annotations

import logging

import pyautogui

logger = logging.getLogger("voiceime.output.keyboard")

# Safety: disable pyautogui failsafe during typing to avoid accidental aborts
# (we're intentionally controlling the keyboard)
pyautogui.PAUSE = 0.02


def type_text(text: str) -> bool:
    """Type text character by character via pyautogui.

    This is the last-resort fallback when clipboard and UIA both fail.
    """
    try:
        pyautogui.write(text, interval=0.01)
        return True
    except Exception:
        # pyautogui.write only handles ASCII; for CJK, use typewrite with unicode
        try:
            pyautogui.typewrite(text, interval=0.01)
            return True
        except Exception as exc:
            logger.error("Keyboard output failed: %s", exc)
            return False
