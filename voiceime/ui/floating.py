"""FloatingBar — topmost overlay for recording feedback and result confirmation."""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _WaveformWidget(QWidget):
    """Custom widget that paints audio level bars."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._levels: list[float] = []
        self.setFixedHeight(32)
        self.setMinimumWidth(120)

    def update_levels(self, levels: list[float]) -> None:
        self._levels = levels[-50:]  # Keep last 50
        self.update()

    def paintEvent(self, event) -> None:
        if not self._levels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_count = len(self._levels)
        bar_width = max(2, w // 50 - 1)

        max_level = max(self._levels) if self._levels else 1.0
        if max_level == 0:
            max_level = 1.0

        for i, level in enumerate(self._levels):
            x = int(i * (w / 50))
            bar_h = int((level / max_level) * (h - 4))
            color = QColor(76, 175, 80) if level / max_level < 0.7 else QColor(255, 193, 7)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(x, h - bar_h - 2, bar_width, bar_h)

        painter.end()


class _RecordingPanel(QWidget):
    """Shows during recording: red indicator + waveform + duration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._indicator = QLabel("●")
        self._indicator.setStyleSheet("color: #f44336; font-size: 16px;")
        layout.addWidget(self._indicator)

        self._waveform = _WaveformWidget()
        layout.addWidget(self._waveform, stretch=1)

        self._duration_label = QLabel("0.0s")
        self._duration_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        layout.addWidget(self._duration_label)

    def update_progress(self, duration_ms: int, levels: list[float]) -> None:
        self._duration_label.setText(f"{duration_ms / 1000:.1f}s")
        self._waveform.update_levels(levels)


class _InferringPanel(QWidget):
    """Shows during ASR inference: spinner + '识别中...' text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)

        label = QLabel("识别中...")
        label.setStyleSheet("color: #ffeb3b; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()


class _ConfirmingPanel(QWidget):
    """Shows ASR result with action buttons."""

    output_requested = pyqtSignal()
    polish_requested = pyqtSignal()
    rerecord_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._text_label = QLabel()
        self._text_label.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        self._text_label.setWordWrap(True)
        self._text_label.setMaximumHeight(60)
        layout.addWidget(self._text_label)

        info_layout = QHBoxLayout()
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        info_layout.addWidget(self._info_label)
        info_layout.addStretch()

        self._output_btn = QPushButton("上屏 (Enter)")
        self._output_btn.clicked.connect(self.output_requested.emit)
        info_layout.addWidget(self._output_btn)

        self._polish_btn = QPushButton("润色 (Alt+E)")
        self._polish_btn.clicked.connect(self.polish_requested.emit)
        info_layout.addWidget(self._polish_btn)

        self._rerecord_btn = QPushButton("重录 (R)")
        self._rerecord_btn.clicked.connect(self.rerecord_requested.emit)
        info_layout.addWidget(self._rerecord_btn)

        self._cancel_btn = QPushButton("取消 (Esc)")
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        info_layout.addWidget(self._cancel_btn)

        layout.addLayout(info_layout)

    def set_result(self, text: str, language: str = "", inference_ms: int = 0,
                   app_name: str = "") -> None:
        self._text_label.setText(text)
        parts = []
        if language:
            parts.append(language)
        if inference_ms:
            parts.append(f"{inference_ms}ms")
        if app_name:
            parts.append(app_name)
        self._info_label.setText(" | ".join(parts) if parts else "")


class FloatingBar(QFrame):
    """Topmost floating overlay with recording/inferring/confirming panels."""

    output_requested = pyqtSignal()
    polish_requested = pyqtSignal()
    rerecord_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Window flags: topmost, frameless, no taskbar entry, no focus steal
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setStyleSheet(
            "FloatingBar { background: #2d2d2d; border: 1px solid #555; border-radius: 8px; }"
        )
        self.setMinimumWidth(360)
        self.setMaximumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create all panels upfront (avoid construction overhead)
        self._recording_panel = _RecordingPanel()
        self._inferring_panel = _InferringPanel()
        self._confirming_panel = _ConfirmingPanel()

        layout.addWidget(self._recording_panel)
        layout.addWidget(self._inferring_panel)
        layout.addWidget(self._confirming_panel)

        # Wire confirming panel signals
        self._confirming_panel.output_requested.connect(self.output_requested.emit)
        self._confirming_panel.polish_requested.connect(self.polish_requested.emit)
        self._confirming_panel.rerecord_requested.connect(self.rerecord_requested.emit)
        self._confirming_panel.cancel_requested.connect(self.cancel_requested.emit)

        self._show_panel(None)
        self.hide()

    def _show_panel(self, panel: QWidget | None) -> None:
        self._recording_panel.setVisible(panel is self._recording_panel)
        self._inferring_panel.setVisible(panel is self._inferring_panel)
        self._confirming_panel.setVisible(panel is self._confirming_panel)

    # ── State-driven display ────────────────────────────

    def show_recording(self) -> None:
        self._show_panel(self._recording_panel)
        self._position_top_center()
        self.show()

    def show_inferring(self) -> None:
        self._show_panel(self._inferring_panel)
        if not self.isVisible():
            self._position_top_center()
            self.show()

    def show_confirming(self, text: str, language: str = "",
                        inference_ms: int = 0, app_name: str = "") -> None:
        self._confirming_panel.set_result(text, language, inference_ms, app_name)
        self._show_panel(self._confirming_panel)
        if not self.isVisible():
            self._position_top_center()
            self.show()

    def hide_bar(self) -> None:
        self.hide()

    # ── Slot: recording progress ────────────────────────

    def on_recording_progress(self, duration_ms: int, levels: list) -> None:
        if self._recording_panel.isVisible():
            self._recording_panel.update_progress(duration_ms, levels)

    # ── Positioning ─────────────────────────────────────

    def _position_top_center(self) -> None:
        from PyQt6.QtGui import QScreen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + 40
            self.move(x, y)

    # ── Keyboard ────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.output_requested.emit()
        elif key == Qt.Key.Key_E and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.polish_requested.emit()
        elif key == Qt.Key.Key_R:
            self.rerecord_requested.emit()
        elif key == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
        else:
            super().keyPressEvent(event)
