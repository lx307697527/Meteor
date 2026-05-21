"""SettingsWindow — VoiceIME settings with tabbed interface (M1.10: Inference Tab)."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from voiceime.config.defaults import DEFAULT_CONFIG
from voiceime.config.manager import ConfigManager
from voiceime.model.manager import ModelManager

logger = logging.getLogger("voiceime.ui.settings")


class _InferenceTab(QWidget):
    """ASR inference engine settings: model, quantization, VAD."""

    def __init__(self, config: ConfigManager, model_mgr: ModelManager | None) -> None:
        super().__init__()
        self._config = config
        self._model_mgr = model_mgr
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Model group
        model_group = QGroupBox("模型设置")
        model_form = QFormLayout()

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.addItems([
            "large-v3-turbo",
            "large-v3",
            "medium",
            "small",
            "base",
            "tiny",
        ])
        model_form.addRow("模型：", self._model_combo)

        self._quant_combo = QComboBox()
        self._quant_combo.addItems(["int8", "float16", "float32"])
        model_form.addRow("量化：", self._quant_combo)

        self._device_combo = QComboBox()
        self._device_combo.addItems(["cpu"])
        model_form.addRow("设备：", self._device_combo)

        self._lang_combo = QComboBox()
        self._lang_combo.setEditable(True)
        self._lang_combo.addItems(["auto", "zh", "en", "ja", "ko"])
        model_form.addRow("语言：", self._lang_combo)

        self._beam_spin = QSpinBox()
        self._beam_spin.setRange(1, 10)
        model_form.addRow("Beam Size：", self._beam_spin)

        model_group.setLayout(model_form)
        layout.addWidget(model_group)

        # VAD group
        vad_group = QGroupBox("VAD 语音活动检测")
        vad_form = QFormLayout()

        self._vad_check = QCheckBox("启用 VAD 过滤")
        vad_form.addRow(self._vad_check)

        self._vad_threshold = QDoubleSpinBox()
        self._vad_threshold.setRange(0.0, 1.0)
        self._vad_threshold.setSingleStep(0.05)
        self._vad_threshold.setDecimals(2)
        vad_form.addRow("VAD 阈值：", self._vad_threshold)

        vad_group.setLayout(vad_form)
        layout.addWidget(vad_group)

        layout.addStretch()

    def _load_values(self) -> None:
        """Load current config values into widgets."""
        self._model_combo.setCurrentText(self._config.get("asr.model", "large-v3-turbo"))
        self._quant_combo.setCurrentText(self._config.get("asr.quantization", "int8"))
        self._device_combo.setCurrentText(self._config.get("asr.device", "cpu"))
        self._lang_combo.setCurrentText(self._config.get("asr.language", "auto"))
        self._beam_spin.setValue(self._config.get("asr.beam_size", 5))
        self._vad_check.setChecked(self._config.get("asr.vad_filter", True))
        self._vad_threshold.setValue(self._config.get("asr.vad_threshold", 0.5))

    def save(self) -> None:
        """Write widget values to config."""
        self._config.set("asr.model", self._model_combo.currentText())
        self._config.set("asr.quantization", self._quant_combo.currentText())
        self._config.set("asr.device", self._device_combo.currentText())
        self._config.set("asr.language", self._lang_combo.currentText())
        self._config.set("asr.beam_size", self._beam_spin.value())
        self._config.set("asr.vad_filter", self._vad_check.isChecked())
        self._config.set("asr.vad_threshold", self._vad_threshold.value())

    def restore_defaults(self) -> None:
        """Reset to default values."""
        defaults = DEFAULT_CONFIG["asr"]
        self._model_combo.setCurrentText(defaults["model"])
        self._quant_combo.setCurrentText(defaults["quantization"])
        self._device_combo.setCurrentText(defaults["device"])
        self._lang_combo.setCurrentText(defaults["language"])
        self._beam_spin.setValue(defaults["beam_size"])
        self._vad_check.setChecked(defaults["vad_filter"])
        self._vad_threshold.setValue(defaults["vad_threshold"])


class SettingsWindow(QDialog):
    """Main settings dialog with tabbed interface."""

    def __init__(self, config: ConfigManager, model_mgr: ModelManager | None = None) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("VoiceIME 设置")
        self.setMinimumSize(520, 480)

        layout = QVBoxLayout(self)

        # Tabs
        self._tabs = QTabWidget()
        self._inference_tab = _InferenceTab(config, model_mgr)
        self._tabs.addTab(self._inference_tab, "推理引擎")
        layout.addWidget(self._tabs)

        # Buttons
        btn_layout = QHBoxLayout()

        self._defaults_btn = QPushButton("恢复默认")
        self._defaults_btn.clicked.connect(self._on_restore_defaults)
        btn_layout.addWidget(self._defaults_btn)

        btn_layout.addStretch()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        btn_layout.addWidget(self._buttons)

        layout.addLayout(btn_layout)

    def _on_accept(self) -> None:
        """Save all tab settings and close."""
        self._inference_tab.save()
        logger.info("Settings saved")
        self.accept()

    def _on_restore_defaults(self) -> None:
        """Restore defaults for the current tab."""
        current = self._tabs.currentWidget()
        if current is self._inference_tab:
            self._inference_tab.restore_defaults()
