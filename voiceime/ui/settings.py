"""SettingsWindow — VoiceIME settings with tabbed interface (5 tabs)."""

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
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
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
        self._beam_spin.setToolTip("越大越准越慢，建议 1-3")
        model_form.addRow("Beam Size：", self._beam_spin)

        self._threads_spin = QSpinBox()
        self._threads_spin.setRange(1, 16)
        self._threads_spin.setToolTip("CPU 推理线程数，建议设为 CPU 逻辑核数的一半")
        model_form.addRow("推理线程：", self._threads_spin)

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
        self._beam_spin.setValue(self._config.get("asr.beam_size", 3))
        self._threads_spin.setValue(self._config.get("asr.cpu_threads", 4))
        self._vad_check.setChecked(self._config.get("asr.vad_filter", True))
        self._vad_threshold.setValue(self._config.get("asr.vad_threshold", 0.5))

    def save(self) -> None:
        """Write widget values to config."""
        self._config.set("asr.model", self._model_combo.currentText())
        self._config.set("asr.quantization", self._quant_combo.currentText())
        self._config.set("asr.device", self._device_combo.currentText())
        self._config.set("asr.language", self._lang_combo.currentText())
        self._config.set("asr.beam_size", self._beam_spin.value())
        self._config.set("asr.cpu_threads", self._threads_spin.value())
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
        self._threads_spin.setValue(defaults["cpu_threads"])
        self._vad_check.setChecked(defaults["vad_filter"])
        self._vad_threshold.setValue(defaults["vad_threshold"])


class _PostProcessTab(QWidget):
    """Post-processing pipeline settings: punctuation, t2s, hotword."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        pipeline_group = QGroupBox("后处理管道")
        form = QFormLayout()

        self._punct_check = QCheckBox("标点规范化")
        self._punct_check.setToolTip("自动补全标点、去除多余空格")
        form.addRow(self._punct_check)

        self._t2s_check = QCheckBox("繁体转简体")
        self._t2s_check.setToolTip("将繁体中文自动转换为简体中文")
        form.addRow(self._t2s_check)

        self._hotword_check = QCheckBox("热词替换")
        self._hotword_check.setToolTip("根据热词词库替换识别结果中的触发词")
        form.addRow(self._hotword_check)

        pipeline_group.setLayout(form)
        layout.addWidget(pipeline_group)
        layout.addStretch()

    def _load_values(self) -> None:
        self._punct_check.setChecked(self._config.get("postprocess.punct_normalize", True))
        self._t2s_check.setChecked(self._config.get("postprocess.t2s_enabled", False))
        self._hotword_check.setChecked(self._config.get("postprocess.hotword_enabled", True))

    def save(self) -> None:
        self._config.set("postprocess.punct_normalize", self._punct_check.isChecked())
        self._config.set("postprocess.t2s_enabled", self._t2s_check.isChecked())
        self._config.set("postprocess.hotword_enabled", self._hotword_check.isChecked())

    def restore_defaults(self) -> None:
        defaults = DEFAULT_CONFIG["postprocess"]
        self._punct_check.setChecked(defaults["punct_normalize"])
        self._t2s_check.setChecked(defaults["t2s_enabled"])
        self._hotword_check.setChecked(defaults["hotword_enabled"])


class _LLMTab(QWidget):
    """LLM integration settings: provider, API key, model, polish mode."""

    def __init__(self, config: ConfigManager, keyring_store=None) -> None:
        super().__init__()
        self._config = config
        self._keyring = keyring_store
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Provider group
        provider_group = QGroupBox("LLM 提供商")
        provider_form = QFormLayout()

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["", "claude", "openai", "ollama"])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_form.addRow("提供商：", self._provider_combo)

        self._model_id_edit = QLineEdit()
        self._model_id_edit.setPlaceholderText("如 claude-sonnet-4-20250514 / gpt-4o-mini / qwen2.5:7b")
        provider_form.addRow("模型 ID：", self._model_id_edit)

        provider_group.setLayout(provider_form)
        layout.addWidget(provider_group)

        # API Key group
        key_group = QGroupBox("API 密钥")
        key_form = QFormLayout()

        self._key_status_label = QLabel("未配置")
        key_form.addRow("状态：", self._key_status_label)

        key_btn_layout = QHBoxLayout()
        self._set_key_btn = QPushButton("设置密钥")
        self._set_key_btn.clicked.connect(self._on_set_key)
        self._delete_key_btn = QPushButton("删除密钥")
        self._delete_key_btn.clicked.connect(self._on_delete_key)
        key_btn_layout.addWidget(self._set_key_btn)
        key_btn_layout.addWidget(self._delete_key_btn)
        key_btn_layout.addStretch()
        key_form.addRow(key_btn_layout)

        key_group.setLayout(key_form)
        layout.addWidget(key_group)

        # Polish group
        polish_group = QGroupBox("润色设置")
        polish_form = QFormLayout()

        self._polish_combo = QComboBox()
        self._polish_combo.addItems(["manual", "auto"])
        polish_form.addRow("润色模式：", self._polish_combo)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMaximumHeight(80)
        self._prompt_edit.setPlaceholderText("自定义系统提示词（留空使用默认）")
        polish_form.addRow("系统提示词：", self._prompt_edit)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 60)
        self._timeout_spin.setSuffix(" 秒")
        polish_form.addRow("超时：", self._timeout_spin)

        polish_group.setLayout(polish_form)
        layout.addWidget(polish_group)
        layout.addStretch()

    def _load_values(self) -> None:
        self._provider_combo.setCurrentText(self._config.get("llm.provider", ""))
        self._model_id_edit.setText(self._config.get("llm.model_id", ""))
        self._polish_combo.setCurrentText(self._config.get("llm.polish_mode", "manual"))
        self._prompt_edit.setPlainText(self._config.get("llm.system_prompt", ""))
        self._timeout_spin.setValue(self._config.get("llm.timeout_seconds", 10))
        self._update_key_status()

    def save(self) -> None:
        self._config.set("llm.provider", self._provider_combo.currentText())
        self._config.set("llm.model_id", self._model_id_edit.text().strip())
        self._config.set("llm.polish_mode", self._polish_combo.currentText())
        self._config.set("llm.system_prompt", self._prompt_edit.toPlainText().strip())
        self._config.set("llm.timeout_seconds", self._timeout_spin.value())

    def restore_defaults(self) -> None:
        defaults = DEFAULT_CONFIG["llm"]
        self._provider_combo.setCurrentText(defaults["provider"])
        self._model_id_edit.setText(defaults["model_id"])
        self._polish_combo.setCurrentText(defaults["polish_mode"])
        self._prompt_edit.setPlainText(defaults["system_prompt"])
        self._timeout_spin.setValue(defaults["timeout_seconds"])

    def _on_provider_changed(self, provider: str) -> None:
        is_ollama = provider == "ollama"
        self._set_key_btn.setEnabled(not is_ollama)
        self._delete_key_btn.setEnabled(not is_ollama)
        self._update_key_status()

    def _update_key_status(self) -> None:
        provider = self._provider_combo.currentText()
        if not provider:
            self._key_status_label.setText("未配置")
            return
        if provider == "ollama":
            self._key_status_label.setText("Ollama 无需密钥")
            return
        if self._keyring and self._keyring.has_key(provider):
            self._key_status_label.setText("已存储 ✓")
        else:
            self._key_status_label.setText("未存储")

    def _on_set_key(self) -> None:
        provider = self._provider_combo.currentText()
        if not provider or provider == "ollama":
            return
        dialog = _ApiKeyDialog(provider, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.api_key:
            if self._keyring:
                self._keyring.save_key(provider, dialog.api_key)
                self._update_key_status()

    def _on_delete_key(self) -> None:
        provider = self._provider_combo.currentText()
        if not provider or provider == "ollama":
            return
        if self._keyring and self._keyring.has_key(provider):
            self._keyring.delete_key(provider)
            self._update_key_status()


class _ApiKeyDialog(QDialog):
    """Simple dialog for entering an API key."""

    def __init__(self, provider: str, parent=None) -> None:
        super().__init__(parent)
        self.api_key = ""
        self.setWindowTitle(f"设置 {provider} API 密钥")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"请输入 {provider} 的 API 密钥："))

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._key_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        self.api_key = self._key_edit.text().strip()
        self.accept()


class _UITab(QWidget):
    """UI behavior settings: quick mode, memory lock, clipboard, recording limits."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Interaction group
        interact_group = QGroupBox("交互")
        interact_form = QFormLayout()

        self._hotkey_combo = QComboBox()
        self._hotkey_combo.addItems([
            "caps_lock", "xbutton1", "xbutton2",
            "f8", "f9", "f10", "f12",
        ])
        self._hotkey_combo.setToolTip(
            "录音快捷键：按住录音，松开上屏。\n"
            "xbutton1 = 鼠标侧键(后退)  xbutton2 = 鼠标侧键(前进)"
        )
        interact_form.addRow("录音快捷键：", self._hotkey_combo)

        self._quick_mode_check = QCheckBox("快速模式")
        self._quick_mode_check.setToolTip("识别完成后跳过确认，直接上屏")
        interact_form.addRow(self._quick_mode_check)

        interact_group.setLayout(interact_form)
        layout.addWidget(interact_group)

        # Memory lock group
        mem_group = QGroupBox("内存锁定")
        mem_form = QFormLayout()

        self._mem_lock_check = QCheckBox("锁定模型内存")
        self._mem_lock_check.setToolTip("使用 VirtualLock 防止模型内存被换出到磁盘")
        mem_form.addRow(self._mem_lock_check)

        self._mem_limit_spin = QDoubleSpinBox()
        self._mem_limit_spin.setRange(1.0, 3.5)
        self._mem_limit_spin.setSingleStep(0.5)
        self._mem_limit_spin.setSuffix(" GB")
        mem_form.addRow("锁定上限：", self._mem_limit_spin)

        mem_group.setLayout(mem_form)
        layout.addWidget(mem_group)

        # Clipboard group
        clip_group = QGroupBox("剪贴板")
        clip_form = QFormLayout()

        self._auto_restore_check = QCheckBox("自动恢复剪贴板")
        self._auto_restore_check.setToolTip("上屏后恢复剪贴板原始内容")
        clip_form.addRow(self._auto_restore_check)

        self._clip_delay_spin = QSpinBox()
        self._clip_delay_spin.setRange(10, 500)
        self._clip_delay_spin.setSuffix(" ms")
        clip_form.addRow("恢复延迟：", self._clip_delay_spin)

        clip_group.setLayout(clip_form)
        layout.addWidget(clip_group)

        # Recording limits group
        rec_group = QGroupBox("录音限制")
        rec_form = QFormLayout()

        self._min_rec_spin = QSpinBox()
        self._min_rec_spin.setRange(100, 1000)
        self._min_rec_spin.setSuffix(" ms")
        rec_form.addRow("最短录音：", self._min_rec_spin)

        self._max_rec_spin = QSpinBox()
        self._max_rec_spin.setRange(5, 300)
        self._max_rec_spin.setSuffix(" 秒")
        rec_form.addRow("最长录音：", self._max_rec_spin)

        rec_group.setLayout(rec_form)
        layout.addWidget(rec_group)
        layout.addStretch()

    def _load_values(self) -> None:
        self._hotkey_combo.setCurrentText(self._config.get("hotkey", "caps_lock"))
        self._quick_mode_check.setChecked(self._config.get("ui.quick_mode", True))
        self._mem_lock_check.setChecked(self._config.get("ui.memory_lock", False))
        self._mem_limit_spin.setValue(self._config.get("ui.memory_lock_limit_gb", 3.5))
        self._auto_restore_check.setChecked(self._config.get("ui.auto_restore_clipboard", True))
        self._clip_delay_spin.setValue(self._config.get("ui.clipboard_restore_delay_ms", 50))
        self._min_rec_spin.setValue(self._config.get("ui.min_record_ms", 200))
        self._max_rec_spin.setValue(self._config.get("ui.max_record_s", 60))

    def save(self) -> None:
        self._config.set("hotkey", self._hotkey_combo.currentText())
        self._config.set("ui.quick_mode", self._quick_mode_check.isChecked())
        self._config.set("ui.memory_lock", self._mem_lock_check.isChecked())
        self._config.set("ui.memory_lock_limit_gb", self._mem_limit_spin.value())
        self._config.set("ui.auto_restore_clipboard", self._auto_restore_check.isChecked())
        self._config.set("ui.clipboard_restore_delay_ms", self._clip_delay_spin.value())
        self._config.set("ui.min_record_ms", self._min_rec_spin.value())
        self._config.set("ui.max_record_s", self._max_rec_spin.value())

    def restore_defaults(self) -> None:
        defaults = DEFAULT_CONFIG
        self._hotkey_combo.setCurrentText(defaults.get("hotkey", "caps_lock"))
        self._quick_mode_check.setChecked(defaults["ui"]["quick_mode"])
        self._mem_lock_check.setChecked(defaults["ui"]["memory_lock"])
        self._mem_limit_spin.setValue(defaults["ui"]["memory_lock_limit_gb"])
        self._auto_restore_check.setChecked(defaults["ui"]["auto_restore_clipboard"])
        self._clip_delay_spin.setValue(defaults["ui"]["clipboard_restore_delay_ms"])
        self._min_rec_spin.setValue(defaults["ui"]["min_record_ms"])
        self._max_rec_spin.setValue(defaults["ui"]["max_record_s"])


class _AdvancedTab(QWidget):
    """Advanced settings: log level, log path."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("日志")
        form = QFormLayout()

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        form.addRow("日志级别：", self._log_level_combo)

        self._log_path_edit = QLineEdit()
        self._log_path_edit.setPlaceholderText("留空使用默认路径 (%APPDATA%\\VoiceIME\\logs)")
        form.addRow("日志路径：", self._log_path_edit)

        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()

    def _load_values(self) -> None:
        self._log_level_combo.setCurrentText(self._config.get("advanced.log_level", "INFO"))
        self._log_path_edit.setText(self._config.get("advanced.log_path", ""))

    def save(self) -> None:
        self._config.set("advanced.log_level", self._log_level_combo.currentText())
        self._config.set("advanced.log_path", self._log_path_edit.text().strip())

    def restore_defaults(self) -> None:
        defaults = DEFAULT_CONFIG["advanced"]
        self._log_level_combo.setCurrentText(defaults["log_level"])
        self._log_path_edit.setText(defaults["log_path"])


class _ContextTab(QWidget):
    """Context-aware behavior settings: enable/disable, rule management."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._rules: list[dict] = []
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Enable group
        enable_group = QGroupBox("上下文感知")
        enable_form = QFormLayout()

        self._enabled_check = QCheckBox("启用上下文感知")
        self._enabled_check.setToolTip("根据当前焦点窗口自动切换后处理行为")
        enable_form.addRow(self._enabled_check)

        enable_group.setLayout(enable_form)
        layout.addWidget(enable_group)

        # Rules table
        rules_group = QGroupBox("规则列表")
        rules_layout = QVBoxLayout()

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["名称", "进程匹配", "标题匹配", "启用"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        rules_layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("编辑")
        self._edit_btn.clicked.connect(self._on_edit)
        self._delete_btn = QPushButton("删除")
        self._delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._edit_btn)
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addStretch()
        rules_layout.addLayout(btn_layout)

        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)
        layout.addStretch()

    def _load_values(self) -> None:
        self._enabled_check.setChecked(self._config.get("context.enabled", True))
        from voiceime.context.rules import ContextRuleRepo
        repo = ContextRuleRepo()
        self._rules = repo.list_all()
        self._refresh_table()

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._rules))
        for i, rule in enumerate(self._rules):
            self._table.setItem(i, 0, QTableWidgetItem(rule.get("name", "")))
            self._table.setItem(i, 1, QTableWidgetItem(rule.get("app_name_pattern", "")))
            self._table.setItem(i, 2, QTableWidgetItem(rule.get("title_pattern", "")))
            enabled = rule.get("enabled", True)
            item = QTableWidgetItem()
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            self._table.setItem(i, 3, item)

    def _current_rule_index(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _on_add(self) -> None:
        dialog = _ContextRuleEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.rule:
            self._rules.append(dialog.rule)
            self._refresh_table()

    def _on_edit(self) -> None:
        idx = self._current_rule_index()
        if idx < 0:
            return
        dialog = _ContextRuleEditDialog(self, self._rules[idx])
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.rule:
            self._rules[idx] = dialog.rule
            self._refresh_table()

    def _on_delete(self) -> None:
        idx = self._current_rule_index()
        if idx < 0:
            return
        name = self._rules[idx].get("name", "")
        reply = QMessageBox.question(
            self, "删除规则", f"确定删除规则「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._rules[idx]
            self._refresh_table()

    def save(self) -> None:
        self._config.set("context.enabled", self._enabled_check.isChecked())
        from voiceime.context.rules import ContextRuleRepo
        repo = ContextRuleRepo()
        repo.set_all(self._rules)

    def restore_defaults(self) -> None:
        defaults = DEFAULT_CONFIG["context"]
        self._enabled_check.setChecked(defaults["enabled"])
        from voiceime.context.rules import ContextRuleRepo
        repo = ContextRuleRepo()
        self._rules = repo._default_rules()
        self._refresh_table()


class _ContextRuleEditDialog(QDialog):
    """Dialog for adding/editing a context rule."""

    def __init__(self, parent=None, rule: dict | None = None) -> None:
        super().__init__(parent)
        self.rule = rule or {}
        self.setWindowTitle("编辑规则" if rule else "添加规则")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit(self.rule.get("name", ""))
        form.addRow("名称：", self._name_edit)

        self._app_edit = QLineEdit(self.rule.get("app_name_pattern", ""))
        self._app_edit.setPlaceholderText("如 code.exe、wechat.exe")
        form.addRow("进程匹配：", self._app_edit)

        self._title_edit = QLineEdit(self.rule.get("title_pattern", ""))
        self._title_edit.setPlaceholderText("留空匹配所有标题")
        form.addRow("标题匹配：", self._title_edit)

        self._enabled_check = QCheckBox("启用")
        self._enabled_check.setChecked(self.rule.get("enabled", True))
        form.addRow(self._enabled_check)

        # Overrides
        ov = self.rule.get("overrides", {})
        ov_group = QGroupBox("行为覆盖")
        ov_form = QFormLayout()

        self._quick_combo = QComboBox()
        self._quick_combo.addItems(["默认", "快速模式", "确认模式"])
        qv = ov.get("quick_mode")
        if qv is True:
            self._quick_combo.setCurrentIndex(1)
        elif qv is False:
            self._quick_combo.setCurrentIndex(2)
        ov_form.addRow("上屏模式：", self._quick_combo)

        self._polish_combo = QComboBox()
        self._polish_combo.addItems(["默认", "手动润色", "自动润色", "关闭润色"])
        pv = ov.get("polish_mode")
        if pv == "manual":
            self._polish_combo.setCurrentIndex(1)
        elif pv == "auto":
            self._polish_combo.setCurrentIndex(2)
        elif pv == "off":
            self._polish_combo.setCurrentIndex(3)
        ov_form.addRow("润色模式：", self._polish_combo)

        self._prompt_combo = QComboBox()
        self._prompt_combo.setEditable(True)
        self._prompt_combo.addItems(["默认", "code_comment", "business"])
        sp = ov.get("system_prompt", "")
        if sp:
            idx = self._prompt_combo.findText(sp)
            if idx >= 0:
                self._prompt_combo.setCurrentIndex(idx)
            else:
                self._prompt_combo.setCurrentText(sp)
        ov_form.addRow("Prompt 模板：", self._prompt_combo)

        ov_group.setLayout(ov_form)
        layout.addLayout(form)
        layout.addWidget(ov_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            return
        overrides: dict = {}
        qi = self._quick_combo.currentIndex()
        if qi == 1:
            overrides["quick_mode"] = True
        elif qi == 2:
            overrides["quick_mode"] = False
        pi = self._polish_combo.currentIndex()
        if pi == 1:
            overrides["polish_mode"] = "manual"
        elif pi == 2:
            overrides["polish_mode"] = "auto"
        elif pi == 3:
            overrides["polish_mode"] = "off"
        prompt = self._prompt_combo.currentText()
        if prompt and prompt != "默认":
            overrides["system_prompt"] = prompt
        self.rule = {
            "name": name,
            "app_name_pattern": self._app_edit.text().strip(),
            "title_pattern": self._title_edit.text().strip(),
            "enabled": self._enabled_check.isChecked(),
            "overrides": overrides,
        }
        self.accept()


class SettingsWindow(QDialog):
    """Main settings dialog with tabbed interface."""

    def __init__(self, config: ConfigManager, model_mgr: ModelManager | None = None, keyring_store=None) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("VoiceIME 设置")
        self.setMinimumSize(560, 520)

        layout = QVBoxLayout(self)

        # Tabs
        self._tabs = QTabWidget()
        self._inference_tab = _InferenceTab(config, model_mgr)
        self._postprocess_tab = _PostProcessTab(config)
        self._llm_tab = _LLMTab(config, keyring_store)
        self._ui_tab = _UITab(config)
        self._advanced_tab = _AdvancedTab(config)
        self._context_tab = _ContextTab(config)
        self._tabs.addTab(self._inference_tab, "推理引擎")
        self._tabs.addTab(self._postprocess_tab, "后处理")
        self._tabs.addTab(self._llm_tab, "LLM 接口")
        self._tabs.addTab(self._ui_tab, "界面与热键")
        self._tabs.addTab(self._advanced_tab, "高级")
        self._tabs.addTab(self._context_tab, "上下文")
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
        self._postprocess_tab.save()
        self._llm_tab.save()
        self._ui_tab.save()
        self._advanced_tab.save()
        self._context_tab.save()
        logger.info("Settings saved")
        self.accept()

    def _on_restore_defaults(self) -> None:
        """Restore defaults for the current tab."""
        current = self._tabs.currentWidget()
        if current is self._inference_tab:
            self._inference_tab.restore_defaults()
        elif current is self._postprocess_tab:
            self._postprocess_tab.restore_defaults()
        elif current is self._llm_tab:
            self._llm_tab.restore_defaults()
        elif current is self._ui_tab:
            self._ui_tab.restore_defaults()
        elif current is self._advanced_tab:
            self._advanced_tab.restore_defaults()
        elif current is self._context_tab:
            self._context_tab.restore_defaults()
