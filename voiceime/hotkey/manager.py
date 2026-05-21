"""HotkeyManager — global hotkey registration and event dispatch."""

from __future__ import annotations

import atexit
import logging
from queue import Queue
from typing import Callable

from voiceime.hotkey.hook import HotkeyConflictError, HotkeyHook
from voiceime.protocols import HotKeyEvent

logger = logging.getLogger("voiceime.hotkey.manager")


class HotkeyManager:
    """Manages global hotkey hook via pynput."""

    def __init__(self, hotkey_name: str = "caps_lock") -> None:
        self._hotkey_name = hotkey_name
        self._hotkey_queue: Queue[HotKeyEvent] = Queue()
        self._on_keydown: Callable[[], None] | None = None
        self._on_keyup: Callable[[], None] | None = None
        self._hook: HotkeyHook | None = None

    @property
    def queue(self) -> Queue[HotKeyEvent]:
        return self._hotkey_queue

    @property
    def current_hotkey(self) -> str:
        return self._hotkey_name

    def set_callback(
        self, on_keydown: Callable[[], None], on_keyup: Callable[[], None]
    ) -> None:
        self._on_keydown = on_keydown
        self._on_keyup = on_keyup

    def start(self) -> None:
        if self._hook is not None:
            return
        self._hook = HotkeyHook(self._hotkey_name, self._hotkey_queue)
        self._hook.start()
        atexit.register(self.stop)
        logger.info("HotkeyManager started with hotkey=%s", self._hotkey_name)

    def stop(self) -> None:
        if self._hook is not None:
            self._hook.stop()
            self._hook = None
        logger.info("HotkeyManager stopped")

    def process_pending_events(self) -> None:
        """Drain all pending hotkey events and fire callbacks. Call from main thread."""
        while not self._hotkey_queue.empty():
            try:
                event = self._hotkey_queue.get_nowait()
            except Exception:
                break
            if event.action == "down" and self._on_keydown:
                self._on_keydown()
            elif event.action == "up" and self._on_keyup:
                self._on_keyup()
