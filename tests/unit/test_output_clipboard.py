"""Clipboard output unit tests — F04+F12: backup/write/paste, clipboard protection."""

from unittest.mock import MagicMock, patch

import pytest


class TestClipboardGuard:
    """ClipboardGuard — backup, write_and_paste, restore cycle."""

    def test_should_backup_existing_clipboard(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.paste", return_value="original"):
            backup = guard.backup()
        assert backup == "original"

    def test_should_return_none_when_clipboard_empty(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.paste", side_effect=Exception("empty")):
            backup = guard.backup()
        assert backup is None

    def test_should_write_and_paste_successfully(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.copy") as mock_copy, \
             patch("voiceime.output.clipboard.pyautogui.hotkey") as mock_hotkey:
            result = guard.write_and_paste("你好世界")
        assert result is True
        mock_copy.assert_called_once_with("你好世界")
        mock_hotkey.assert_called_once_with("ctrl", "v")

    def test_should_return_false_when_write_fails(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.copy", side_effect=OSError("fail")):
            result = guard.write_and_paste("test")
        assert result is False

    def test_should_restore_backup_after_delay(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.copy") as mock_copy:
            result = guard.restore("saved text")
        assert result is True
        mock_copy.assert_called_with("saved text")

    def test_should_succeed_when_restoring_none(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        result = guard.restore(None)
        assert result is True

    def test_should_return_false_when_restore_fails(self):
        from voiceime.output.clipboard import ClipboardGuard

        guard = ClipboardGuard(restore_delay_ms=10)
        with patch("voiceime.output.clipboard.pyperclip.copy", side_effect=OSError("fail")):
            result = guard.restore("text")
        assert result is False
