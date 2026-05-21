"""Hotkey hook — pynput Listener wrapper for keyboard and mouse hotkeys."""

from __future__ import annotations

import logging
from queue import Queue

from pynput import keyboard, mouse

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

# Map config hotkey names to pynput mouse buttons
_MOUSE_MAP: dict[str, mouse.Button] = {
    "xbutton1": mouse.Button.x1,
    "xbutton2": mouse.Button.x2,
}


class HotkeyConflictError(Exception):
    pass


class HookRegistrationError(Exception):
    pass


class HotkeyHook:
    """Wraps pynput keyboard/mouse listener for global hotkey capture."""

    def __init__(self, hotkey_name: str, event_queue: Queue[HotKeyEvent]) -> None:
        self._hotkey_name = hotkey_name
        self._target_key = _HOTKEY_MAP.get(hotkey_name)
        self._target_button = _MOUSE_MAP.get(hotkey_name)

        if self._target_key is None and self._target_button is None:
            raise HotkeyConflictError(f"Unsupported hotkey: {hotkey_name}")

        self._queue = event_queue
        self._kb_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._suppress_caps_lock = hotkey_name == "caps_lock"
        self._is_mouse = self._target_button is not None

    @property
    def is_mouse(self) -> bool:
        return self._is_mouse

    def start(self) -> None:
        if self._is_mouse:
            self._start_mouse()
        else:
            self._start_keyboard()

    def _start_keyboard(self) -> None:
        if self._kb_listener is not None:
            return
        try:
            self._kb_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False,
            )
            self._kb_listener.start()
            logger.info("Hotkey hook started (keyboard) for %s", self._hotkey_name)
        except Exception as exc:
            self._kb_listener = None
            raise HookRegistrationError(f"Failed to register keyboard hook: {exc}") from exc

    def _start_mouse(self) -> None:
        if self._mouse_listener is not None:
            return
        try:
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
            )
            self._mouse_listener.start()
            logger.info("Hotkey hook started (mouse) for %s", self._hotkey_name)
        except Exception as exc:
            self._mouse_listener = None
            raise HookRegistrationError(f"Failed to register mouse hook: {exc}") from exc

    def stop(self) -> None:
        if self._kb_listener is not None:
            self._kb_listener.stop()
            self._kb_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        logger.info("Hotkey hook stopped")

    def _on_press(self, key) -> None:
        if self._match(key):
            self._queue.put(HotKeyEvent(key=self._hotkey_name, action="down"))
            return False if self._suppress_caps_lock else None

    def _on_release(self, key) -> None:
        if self._match(key):
            self._queue.put(HotKeyEvent(key=self._hotkey_name, action="up"))
            return False if self._suppress_caps_lock else None

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        if button == self._target_button:
            action = "down" if pressed else "up"
            self._queue.put(HotKeyEvent(key=self._hotkey_name, action=action))

    def _match(self, key) -> bool:
        if isinstance(key, keyboard.Key):
            return key == self._target_key
        return False
