"""HotkeyManager unit tests — F01: hotkey dispatch, callback, filtering."""

from queue import Queue
from unittest.mock import MagicMock

import pytest

from voiceime.hotkey.manager import HotkeyManager
from voiceime.protocols import HotKeyEvent


class TestHotkeyManager:
    """HotkeyManager — queue-based event dispatch."""

    def test_should_invoke_on_keydown_when_down_event_processed(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        on_down = MagicMock()
        on_up = MagicMock()
        mgr.set_callback(on_keydown=on_down, on_keyup=on_up)

        mgr.queue.put(HotKeyEvent(key="caps_lock", action="down"))
        mgr.process_pending_events()

        on_down.assert_called_once()
        on_up.assert_not_called()

    def test_should_invoke_on_keyup_when_up_event_processed(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        on_down = MagicMock()
        on_up = MagicMock()
        mgr.set_callback(on_keydown=on_down, on_keyup=on_up)

        mgr.queue.put(HotKeyEvent(key="caps_lock", action="up"))
        mgr.process_pending_events()

        on_up.assert_called_once()
        on_down.assert_not_called()

    def test_should_process_multiple_events_in_order(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        on_down = MagicMock()
        on_up = MagicMock()
        mgr.set_callback(on_keydown=on_down, on_keyup=on_up)

        mgr.queue.put(HotKeyEvent(key="caps_lock", action="down"))
        mgr.queue.put(HotKeyEvent(key="caps_lock", action="up"))
        mgr.process_pending_events()

        assert on_down.call_count == 1
        assert on_up.call_count == 1

    def test_should_return_current_hotkey_name(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        assert mgr.current_hotkey == "caps_lock"

    def test_should_ignore_events_when_no_callback_set(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        mgr.queue.put(HotKeyEvent(key="caps_lock", action="down"))
        # Should not raise
        mgr.process_pending_events()

    def test_should_drain_all_pending_events(self):
        mgr = HotkeyManager(hotkey_name="caps_lock")
        mgr.set_callback(on_keydown=MagicMock(), on_keyup=MagicMock())

        for _ in range(5):
            mgr.queue.put(HotKeyEvent(key="caps_lock", action="down"))
        mgr.process_pending_events()

        assert mgr.queue.empty()

    def test_should_start_and_stop_hook(self):
        from unittest.mock import patch

        mgr = HotkeyManager(hotkey_name="caps_lock")
        with patch("pynput.keyboard.Listener") as mock_listener:
            mock_listener.return_value.start = MagicMock()
            mock_listener.return_value.stop = MagicMock()
            mgr.start()
            mgr.stop()
