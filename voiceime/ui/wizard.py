"""FirstRunWizard — 3-step onboarding: mic check → model download → hotkey confirm."""

from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QWizard,
    QWizardPage,
)

from voiceime.config.manager import ConfigManager
from voiceime.model.manager import ModelManager
from voiceime.protocols import DeviceInfo
from voiceime.recorder.device import list_devices

logger = logging.getLogger("voiceime.ui.wizard")


class _MicCheckPage(QWizardPage):
    """Step 1: Microphone device detection."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("麦克风检测")
        self.setSubTitle("检测系统中的麦克风设备")

        self._devices: list[DeviceInfo] = []
        self._info_label = QLabel("正在检测...")
        self._info_label.setWordWrap(True)
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self._info_label)

    def initializePage(self) -> None:
        self._devices = list_devices()
        if self._devices:
            lines = [f"  - {d.name}" + (" (默认)" if d.is_default else "") for d in self._devices]
            self._info_label.setText(f"检测到 {len(self._devices)} 个麦克风设备：\n" + "\n".join(lines))
            self.completeChanged.emit()
        else:
            self._info_label.setText("未检测到麦克风设备。\n请连接麦克风后点击「上一步」重新检测。")

    def isComplete(self) -> bool:
        return len(self._devices) > 0


class _ModelDownloadPage(QWizardPage):
    """Step 2: Download ASR model with progress bar."""

    download_finished = pyqtSignal(bool, str)  # success, error_message

    def __init__(self, model_mgr: ModelManager, config: ConfigManager) -> None:
        super().__init__()
        self._model_mgr = model_mgr
        self._config = config
        self._success = False
        self._error_msg = ""
        self._started = False

        self.setTitle("下载语音模型")
        self.setSubTitle("下载 faster-whisper 语音识别模型（首次使用需要下载）")

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)

        self._status = QLabel("准备下载...")
        self._status.setWordWrap(True)

        layout = QHBoxLayout()
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        self.setLayout(layout)

        self.download_finished.connect(self._on_download_finished)

    def initializePage(self) -> None:
        self._started = False
        self._success = False
        self._progress.setValue(0)
        self.completeChanged.emit()

    def validatePage(self) -> bool:
        return self._success

    def isComplete(self) -> bool:
        return self._success

    def _start_download(self) -> None:
        if self._started:
            return
        self._started = True
        self._status.setText("正在下载模型，请耐心等待...")
        # Indeterminate mode until progress data arrives
        self._progress.setRange(0, 0)

        model_name = self._config.get("asr.model", "large-v3-turbo")
        quantization = self._config.get("asr.quantization", "int8")

        def _download():
            try:
                self._model_mgr.ensure_model(model_name, quantization)
                self.download_finished.emit(True, "")
            except Exception as exc:
                logger.error("Model download failed: %s", exc)
                self.download_finished.emit(False, str(exc))

        threading.Thread(target=_download, daemon=True).start()
        self._poll_progress()

    def _poll_progress(self) -> None:
        if self._success:
            return

        progress = self._model_mgr.download_progress
        if progress and progress.total_bytes > 0:
            # Switch to determinate mode once we have real data
            if self._progress.minimum() == 0 and self._progress.maximum() == 0:
                self._progress.setRange(0, 100)
            pct = int(progress.downloaded_bytes / progress.total_bytes * 100)
            self._progress.setValue(pct)
            if progress.speed_bps > 0:
                speed_mb = progress.speed_bps / (1024 * 1024)
                self._status.setText(f"下载中... {pct}% ({speed_mb:.1f} MB/s)")
            else:
                self._status.setText(f"下载中... {pct}%")
        else:
            self._status.setText("正在下载模型文件...")

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self._poll_progress)

    def _on_download_finished(self, success: bool, error_msg: str) -> None:
        self._success = success
        self._error_msg = error_msg
        if success:
            self._progress.setValue(100)
            self._status.setText("模型下载完成！")
        else:
            self._status.setText(f"下载失败：{error_msg}")
            QMessageBox.warning(self, "下载失败", f"模型下载失败：{error_msg}")
        self.completeChanged.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._start_download()


class _HotkeyConfirmPage(QWizardPage):
    """Step 3: Hotkey usage explanation."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self.setTitle("快捷键说明")
        self.setSubTitle("了解如何使用语音输入")

        hotkey_name = config.get("hotkey", "caps_lock")
        hotkey_label = "Caps Lock" if hotkey_name == "caps_lock" else hotkey_name

        self._info_label = QLabel(
            f"语音输入快捷键：{hotkey_label}\n\n"
            "使用方式：\n"
            f"  1. 按住 {hotkey_label} 开始录音\n"
            f"  2. 松开 {hotkey_label} 结束录音\n"
            "  3. 等待识别完成后自动输入文字\n\n"
            "提示：可以在系统托盘图标右键菜单中暂停/恢复或更改设置。"
        )
        self._info_label.setWordWrap(True)
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self._info_label)


class FirstRunWizard(QWizard):
    """First-run setup wizard with mic check, model download, and hotkey info."""

    def __init__(self, config: ConfigManager, model_mgr: ModelManager) -> None:
        super().__init__()
        self.setWindowTitle("VoiceIME 首次设置")
        self.setMinimumSize(560, 400)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)

        self.addPage(_MicCheckPage())
        self.addPage(_ModelDownloadPage(model_mgr, config))
        self.addPage(_HotkeyConfirmPage(config))

    def mark_complete(self, config: ConfigManager) -> None:
        """Write first_run_complete flag to config."""
        config.set("first_run_complete", True)
