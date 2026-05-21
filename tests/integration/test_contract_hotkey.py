"""CONTRACT-01: HotkeyProvider protocol compliance."""

from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import HotkeyProvider


class TestContractHotkeyProvider:
    """Verify HotkeyManager satisfies HotkeyProvider protocol."""

    def test_should_satisfy_protocol_interface(self):
        from voiceime.hotkey.manager import HotkeyManager

        mgr = HotkeyManager(hotkey_name="caps_lock")
        # Structural subtyping — check all methods exist with correct signatures
        assert callable(getattr(mgr, "start", None))
        assert callable(getattr(mgr, "stop", None))
        assert callable(getattr(mgr, "set_callback", None))

    def test_should_have_required_methods(self):
        from voiceime.hotkey.manager import HotkeyManager

        mgr = HotkeyManager(hotkey_name="caps_lock")
        assert hasattr(mgr, "start")
        assert hasattr(mgr, "stop")
        assert hasattr(mgr, "set_callback")
        assert hasattr(mgr, "current_hotkey")

    def test_should_start_and_stop_without_error(self):
        from voiceime.hotkey.manager import HotkeyManager

        mgr = HotkeyManager(hotkey_name="caps_lock")
        with patch("pynput.keyboard.Listener") as mock_listener:
            mock_listener.return_value.start = MagicMock()
            mock_listener.return_value.stop = MagicMock()
            mgr.start()
            mgr.stop()

    def test_should_dispatch_events_to_callbacks(self):
        from voiceime.hotkey.manager import HotkeyManager
        from voiceime.protocols import HotKeyEvent

        mgr = HotkeyManager(hotkey_name="caps_lock")
        on_down = MagicMock()
        on_up = MagicMock()
        mgr.set_callback(on_keydown=on_down, on_keyup=on_up)

        mgr.queue.put(HotKeyEvent(key="caps_lock", action="down"))
        mgr.queue.put(HotKeyEvent(key="caps_lock", action="up"))
        mgr.process_pending_events()

        on_down.assert_called_once()
        on_up.assert_called_once()
