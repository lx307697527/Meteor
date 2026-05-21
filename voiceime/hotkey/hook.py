"""Hotkey hook — pynput Listener wrapper."""

from __future__ import annotations

import logging
from queue import Queue

from pynput import keyboard

from voiceime.protocols import HotKeyEvent

logger = logging.getLogger("voiceime.hotkey.hook")

# Map config hotkey names to pynput key objects
_HOTKEY_MAP: dict[str, keyboard.Key] = {
    "caps_lock": keyboard.Key.caps_lock,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f12": keyboard.Key.f12,
}


class HotkeyConflictError(Exception):
    pass


class HookRegistrationError(Exception):
    pass


class HotkeyHook:
    """Wraps pynput.keyboard.Listener for global hotkey capture."""

    def __init__(self, hotkey_name: str, event_queue: Queue[HotKeyEvent]) -> None:
        self._hotkey_name = hotkey_name
        self._target_key = _HOTKEY_MAP.get(hotkey_name)
        if self._target_key is None:
            raise HotkeyConflictError(f"Unsupported hotkey: {hotkey_name}")

        self._queue = event_queue
        self._listener: keyboard.Listener | None = None
        self._suppress_caps_lock = hotkey_name == "caps_lock"

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False,
            )
            self._listener.start()
            logger.info("Hotkey hook started for %s", self._hotkey_name)
        except Exception as exc:
            self._listener = None
            raise HookRegistrationError(f"Failed to register hook: {exc}") from exc

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey hook stopped")

    def _on_press(self, key) -> None:
        if self._match(key):
            self._queue.put(HotKeyEvent(key=self._hotkey_name, action="down"))
            # Suppress Caps Lock toggle when used as hotkey
            return False if self._suppress_caps_lock else None

    def _on_release(self, key) -> None:
        if self._match(key):
            self._queue.put(HotKeyEvent(key=self._hotkey_name, action="up"))
            return False if self._suppress_caps_lock else None

    def _match(self, key) -> bool:
        if isinstance(key, keyboard.Key):
            return key == self._target_key
        return False
