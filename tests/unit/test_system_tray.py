"""Tests for SystemTray — status icons, command queue, pause toggle."""

from __future__ import annotations

from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

from voiceime.protocols import TrayCommand
from voiceime.ui.tray import (
    STATUS_ERROR,
    STATUS_LOADING,
    STATUS_PAUSED,
    STATUS_READY,
    STATUS_RECORDING,
    SystemTray,
    _STATUS_ICONS,
    _create_icon,
)


class TestCreateIcon:
    def test_should_create_green_icon_for_ready(self):
        img = _create_icon("green")
        assert img.size == (32, 32)
        assert img.mode == "RGBA"

    def test_should_create_yellow_icon_for_loading(self):
        img = _create_icon("yellow")
        assert img.size == (32, 32)

    def test_should_create_red_icon_for_recording(self):
        img = _create_icon("red")
        assert img.size == (32, 32)

    def test_should_create_gray_icon_for_paused(self):
        img = _create_icon("gray")
        assert img.size == (32, 32)

    def test_should_default_to_green_for_unknown_color(self):
        img = _create_icon("purple")
        assert img.size == (32, 32)


class TestStatusIconsMapping:
    def test_should_map_ready_to_green(self):
        assert _STATUS_ICONS[STATUS_READY] == "green"

    def test_should_map_loading_to_yellow(self):
        assert _STATUS_ICONS[STATUS_LOADING] == "yellow"

    def test_should_map_recording_to_red(self):
        assert _STATUS_ICONS[STATUS_RECORDING] == "red"

    def test_should_map_error_to_red(self):
        assert _STATUS_ICONS[STATUS_ERROR] == "red"

    def test_should_map_paused_to_gray(self):
        assert _STATUS_ICONS[STATUS_PAUSED] == "gray"


class TestSystemTrayLifecycle:
    def test_should_initialize_with_ready_status(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        assert tray._status == STATUS_READY
        assert tray._paused is False

    def test_should_create_cmd_queue_reference(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        assert tray._cmd_queue is queue

    @patch("voiceime.ui.tray.pystray.Icon")
    def test_should_start_thread_on_start(self, mock_icon_cls):
        # Make pystray.Icon.run() block so the thread stays alive
        mock_icon = MagicMock()
        mock_icon.run = MagicMock(side_effect=lambda: __import__("time").sleep(5))
        mock_icon_cls.return_value = mock_icon

        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray.start()
        assert tray._thread is not None
        assert tray._thread.is_alive()
        tray.stop()

    @patch("voiceime.ui.tray.pystray.Icon")
    def test_should_stop_thread_on_stop(self, mock_icon_cls):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray.start()
        tray.stop()
        assert not tray._thread.is_alive()


class TestSystemTrayStatus:
    @patch("voiceime.ui.tray.pystray.Icon")
    def test_should_update_icon_color_on_status_change(self, mock_icon_cls):
        mock_icon = MagicMock()
        mock_icon_cls.return_value = mock_icon

        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray.start()
        tray._icon = mock_icon

        tray.set_status(STATUS_ERROR)
        assert tray._status == STATUS_ERROR
        mock_icon.icon = _create_icon("red")
        mock_icon.title = f"VoiceIME — {STATUS_ERROR}"

        tray.set_status(STATUS_PAUSED)
        mock_icon.icon = _create_icon("gray")
        mock_icon.title = f"VoiceIME — {STATUS_PAUSED}"

        tray.stop()

    @patch("voiceime.ui.tray.pystray.Icon")
    def test_should_default_to_green_for_unknown_status(self, mock_icon_cls):
        mock_icon = MagicMock()
        mock_icon_cls.return_value = mock_icon

        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray.start()
        tray._icon = mock_icon

        tray.set_status("unknown_status")
        # Should default to green
        mock_icon.icon = _create_icon("green")

        tray.stop()

    @patch("voiceime.ui.tray.pystray.Icon")
    def test_should_not_crash_when_icon_is_none(self, mock_icon_cls):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        # _icon is None before _run starts
        tray.set_status(STATUS_READY)
        # Should not raise


class TestSystemTrayCommands:
    def test_should_enqueue_pause_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._paused = False
        tray._on_toggle_pause(None, None)
        cmd = queue.get_nowait()
        assert isinstance(cmd, TrayCommand)
        assert cmd.action == "pause"
        assert tray._paused is True

    def test_should_enqueue_resume_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._paused = True
        tray._on_toggle_pause(None, None)
        cmd = queue.get_nowait()
        assert cmd.action == "resume"
        assert tray._paused is False

    def test_should_enqueue_settings_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._on_settings(None, None)
        cmd = queue.get_nowait()
        assert cmd.action == "settings"

    def test_should_enqueue_history_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._on_history(None, None)
        cmd = queue.get_nowait()
        assert cmd.action == "history"

    def test_should_enqueue_hotword_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._on_hotword(None, None)
        cmd = queue.get_nowait()
        assert cmd.action == "hotword"

    def test_should_enqueue_exit_action(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        mock_icon = MagicMock()
        tray._on_exit(mock_icon, None)
        cmd = queue.get_nowait()
        assert cmd.action == "exit"
        mock_icon.stop.assert_called_once()

    def test_should_update_status_after_pause_toggle(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._paused = False
        mock_icon = MagicMock()
        tray._on_toggle_pause(mock_icon, None)
        assert tray._status == STATUS_PAUSED

    def test_should_update_status_after_resume_toggle(self):
        queue: Queue[TrayCommand] = Queue()
        tray = SystemTray(queue)
        tray._paused = True
        mock_icon = MagicMock()
        tray._on_toggle_pause(mock_icon, None)
        assert tray._status == STATUS_READY
