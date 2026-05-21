"""Tests for FloatingBar — state transitions, waveform, button signals."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from voiceime.ui.floating import FloatingBar


@pytest.fixture
def floating_bar(qapp):
    bar = FloatingBar()
    yield bar
    bar.hide()


class TestFloatingBarStates:
    def test_should_show_recording_panel_when_recording(self, floating_bar):
        floating_bar.show_recording()
        assert floating_bar.isVisible()
        assert floating_bar._recording_panel.isVisible()
        assert not floating_bar._inferring_panel.isVisible()
        assert not floating_bar._confirming_panel.isVisible()

    def test_should_show_inferring_panel_when_inferring(self, floating_bar):
        floating_bar.show_inferring()
        assert floating_bar.isVisible()
        assert floating_bar._inferring_panel.isVisible()
        assert not floating_bar._recording_panel.isVisible()

    def test_should_show_confirming_panel_with_text(self, floating_bar):
        floating_bar.show_confirming("你好世界", language="zh", inference_ms=1200)
        assert floating_bar.isVisible()
        assert floating_bar._confirming_panel.isVisible()
        assert "你好世界" in floating_bar._confirming_panel._text_label.text()

    def test_should_hide_bar(self, floating_bar):
        floating_bar.show_recording()
        floating_bar.hide_bar()
        assert not floating_bar.isVisible()

    def test_should_update_waveform_on_recording_progress(self, floating_bar):
        floating_bar.show_recording()
        levels = [0.1, 0.5, 0.3, 0.8]
        floating_bar.on_recording_progress(1000, levels)
        # Verify the waveform widget received the levels
        assert floating_bar._recording_panel._waveform._levels == levels

    def test_should_not_update_waveform_when_not_recording(self, floating_bar):
        floating_bar.show_inferring()
        floating_bar.on_recording_progress(1000, [0.5])
        # Waveform should remain empty since recording panel is not visible
        assert floating_bar._recording_panel._waveform._levels == []


class TestFloatingBarSignals:
    def test_should_emit_output_requested_on_enter(self, floating_bar):
        floating_bar.show_confirming("test")
        received = []
        floating_bar.output_requested.connect(lambda: received.append(True))
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
        floating_bar.keyPressEvent(event)
        assert len(received) == 1

    def test_should_emit_cancel_requested_on_esc(self, floating_bar):
        floating_bar.show_confirming("test")
        received = []
        floating_bar.cancel_requested.connect(lambda: received.append(True))
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        floating_bar.keyPressEvent(event)
        assert len(received) == 1

    def test_should_emit_rerecord_requested_on_r(self, floating_bar):
        floating_bar.show_confirming("test")
        received = []
        floating_bar.rerecord_requested.connect(lambda: received.append(True))
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier
        )
        floating_bar.keyPressEvent(event)
        assert len(received) == 1
