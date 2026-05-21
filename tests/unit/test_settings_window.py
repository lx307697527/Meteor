"""Tests for SettingsWindow — tab UI, save/restore, config persistence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QTabWidget

from voiceime.ui.settings import (
    SettingsWindow,
    _AdvancedTab,
    _ApiKeyDialog,
    _InferenceTab,
    _LLMTab,
    _PostProcessTab,
    _UITab,
)


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    """All settings tests need a QApplication."""


@pytest.fixture
def settings_window(config_manager, qapp):
    model_mgr = MagicMock()
    keyring_store = MagicMock()
    win = SettingsWindow(config_manager, model_mgr, keyring_store)
    yield win
    win.close()


class TestInferenceTab:
    def test_should_load_config_values_into_widgets(self, config_manager):
        config_manager.set("asr.model", "base")
        config_manager.set("asr.vad_filter", False)
        tab = _InferenceTab(config_manager, None)
        assert tab._model_combo.currentText() == "base"
        assert tab._vad_check.isChecked() is False

    def test_should_save_widget_values_to_config(self, config_manager):
        tab = _InferenceTab(config_manager, None)
        tab._model_combo.setCurrentText("tiny")
        tab._vad_check.setChecked(True)
        tab._vad_threshold.setValue(0.75)
        tab.save()
        assert config_manager.get("asr.model") == "tiny"
        assert config_manager.get("asr.vad_filter") is True
        assert config_manager.get("asr.vad_threshold") == 0.75

    def test_should_restore_defaults(self, config_manager):
        config_manager.set("asr.model", "tiny")
        tab = _InferenceTab(config_manager, None)
        tab.restore_defaults()
        assert tab._model_combo.currentText() == "large-v3-turbo"
        assert tab._vad_check.isChecked() is True

    def test_should_have_model_combo_with_expected_models(self, config_manager):
        tab = _InferenceTab(config_manager, None)
        items = [tab._model_combo.itemText(i) for i in range(tab._model_combo.count())]
        assert "large-v3-turbo" in items
        assert "tiny" in items

    def test_should_have_quantization_options(self, config_manager):
        tab = _InferenceTab(config_manager, None)
        items = [tab._quant_combo.itemText(i) for i in range(tab._quant_combo.count())]
        assert "int8" in items
        assert "float16" in items


class TestPostProcessTab:
    def test_should_load_config_values(self, config_manager):
        config_manager.set("postprocess.t2s_enabled", True)
        tab = _PostProcessTab(config_manager)
        assert tab._t2s_check.isChecked() is True
        assert tab._punct_check.isChecked() is True
        assert tab._hotword_check.isChecked() is True

    def test_should_save_widget_values_to_config(self, config_manager):
        tab = _PostProcessTab(config_manager)
        tab._t2s_check.setChecked(True)
        tab._punct_check.setChecked(False)
        tab.save()
        assert config_manager.get("postprocess.t2s_enabled") is True
        assert config_manager.get("postprocess.punct_normalize") is False

    def test_should_restore_defaults(self, config_manager):
        config_manager.set("postprocess.t2s_enabled", True)
        tab = _PostProcessTab(config_manager)
        tab.restore_defaults()
        assert tab._t2s_check.isChecked() is False


class TestLLMTab:
    def test_should_load_config_values(self, config_manager):
        config_manager.set("llm.provider", "openai")
        config_manager.set("llm.model_id", "gpt-4o")
        config_manager.set("llm.polish_mode", "auto")
        tab = _LLMTab(config_manager, None)
        assert tab._provider_combo.currentText() == "openai"
        assert tab._model_id_edit.text() == "gpt-4o"
        assert tab._polish_combo.currentText() == "auto"

    def test_should_save_widget_values_to_config(self, config_manager):
        tab = _LLMTab(config_manager, None)
        tab._provider_combo.setCurrentText("claude")
        tab._model_id_edit.setText("claude-sonnet-4-20250514")
        tab._timeout_spin.setValue(15)
        tab.save()
        assert config_manager.get("llm.provider") == "claude"
        assert config_manager.get("llm.model_id") == "claude-sonnet-4-20250514"
        assert config_manager.get("llm.timeout_seconds") == 15

    def test_should_restore_defaults(self, config_manager):
        config_manager.set("llm.provider", "claude")
        tab = _LLMTab(config_manager, None)
        tab.restore_defaults()
        assert tab._provider_combo.currentText() == ""
        assert tab._timeout_spin.value() == 10

    def test_should_disable_key_buttons_for_ollama(self, config_manager):
        tab = _LLMTab(config_manager, None)
        tab._provider_combo.setCurrentText("ollama")
        assert not tab._set_key_btn.isEnabled()
        assert not tab._delete_key_btn.isEnabled()

    def test_should_enable_key_buttons_for_openai(self, config_manager):
        tab = _LLMTab(config_manager, None)
        tab._provider_combo.setCurrentText("openai")
        assert tab._set_key_btn.isEnabled()
        assert tab._delete_key_btn.isEnabled()

    def test_should_show_key_status_when_keyring_has_key(self, config_manager):
        keyring = MagicMock()
        keyring.has_key.return_value = True
        tab = _LLMTab(config_manager, keyring)
        tab._provider_combo.setCurrentText("openai")
        tab._update_key_status()
        assert "已存储" in tab._key_status_label.text()

    def test_should_show_not_stored_when_no_key(self, config_manager):
        keyring = MagicMock()
        keyring.has_key.return_value = False
        tab = _LLMTab(config_manager, keyring)
        tab._provider_combo.setCurrentText("openai")
        tab._update_key_status()
        assert "未存储" in tab._key_status_label.text()

    def test_should_save_key_via_keyring_on_accept(self, config_manager):
        keyring = MagicMock()
        tab = _LLMTab(config_manager, keyring)
        tab._provider_combo.setCurrentText("openai")
        dialog = _ApiKeyDialog("openai", tab)
        dialog._key_edit.setText("sk-test-key-123")
        dialog._on_accept()
        assert dialog.api_key == "sk-test-key-123"
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_should_delete_key_via_keyring(self, config_manager):
        keyring = MagicMock()
        keyring.has_key.return_value = True
        tab = _LLMTab(config_manager, keyring)
        tab._provider_combo.setCurrentText("openai")
        tab._on_delete_key()
        keyring.delete_key.assert_called_once_with("openai")


class TestUITab:
    def test_should_load_config_values(self, config_manager):
        config_manager.set("ui.quick_mode", False)
        config_manager.set("ui.memory_lock", True)
        config_manager.set("ui.min_record_ms", 300)
        tab = _UITab(config_manager)
        assert tab._quick_mode_check.isChecked() is False
        assert tab._mem_lock_check.isChecked() is True
        assert tab._min_rec_spin.value() == 300

    def test_should_save_widget_values_to_config(self, config_manager):
        tab = _UITab(config_manager)
        tab._quick_mode_check.setChecked(False)
        tab._mem_lock_check.setChecked(True)
        tab._mem_limit_spin.setValue(2.0)
        tab._clip_delay_spin.setValue(100)
        tab.save()
        assert config_manager.get("ui.quick_mode") is False
        assert config_manager.get("ui.memory_lock") is True
        assert config_manager.get("ui.memory_lock_limit_gb") == 2.0
        assert config_manager.get("ui.clipboard_restore_delay_ms") == 100

    def test_should_restore_defaults(self, config_manager):
        config_manager.set("ui.quick_mode", False)
        tab = _UITab(config_manager)
        tab.restore_defaults()
        assert tab._quick_mode_check.isChecked() is True
        assert tab._mem_lock_check.isChecked() is False

    def test_should_have_valid_spin_ranges(self):
        tab = _UITab(MagicMock())
        assert tab._min_rec_spin.minimum() == 100
        assert tab._min_rec_spin.maximum() == 1000
        assert tab._max_rec_spin.minimum() == 5
        assert tab._max_rec_spin.maximum() == 300
        assert tab._mem_limit_spin.minimum() == 1.0
        assert tab._mem_limit_spin.maximum() == 3.5


class TestAdvancedTab:
    def test_should_load_config_values(self, config_manager):
        config_manager.set("advanced.log_level", "DEBUG")
        config_manager.set("advanced.log_path", "C:\\logs")
        tab = _AdvancedTab(config_manager)
        assert tab._log_level_combo.currentText() == "DEBUG"
        assert tab._log_path_edit.text() == "C:\\logs"

    def test_should_save_widget_values_to_config(self, config_manager):
        tab = _AdvancedTab(config_manager)
        tab._log_level_combo.setCurrentText("ERROR")
        tab._log_path_edit.setText("D:\\mylogs")
        tab.save()
        assert config_manager.get("advanced.log_level") == "ERROR"
        assert config_manager.get("advanced.log_path") == "D:\\mylogs"

    def test_should_restore_defaults(self, config_manager):
        config_manager.set("advanced.log_level", "DEBUG")
        tab = _AdvancedTab(config_manager)
        tab.restore_defaults()
        assert tab._log_level_combo.currentText() == "INFO"
        assert tab._log_path_edit.text() == ""


class TestSettingsWindow:
    def test_should_have_all_six_tabs(self, settings_window):
        tabs = settings_window._tabs
        assert tabs.count() == 6
        assert tabs.tabText(0) == "推理引擎"
        assert tabs.tabText(1) == "后处理"
        assert tabs.tabText(2) == "LLM 接口"
        assert tabs.tabText(3) == "界面与热键"
        assert tabs.tabText(4) == "高级"
        assert tabs.tabText(5) == "上下文"

    def test_should_save_all_tabs_on_accept(self, config_manager):
        config_manager.set("asr.model", "large-v3-turbo")
        config_manager.set("ui.quick_mode", True)
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        # Change a value
        win._inference_tab._model_combo.setCurrentText("base")
        win._on_accept()
        assert config_manager.get("asr.model") == "base"

    def test_should_restore_defaults_for_current_tab(self, config_manager):
        config_manager.set("asr.model", "tiny")
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        win._tabs.setCurrentIndex(0)  # Inference tab
        win._on_restore_defaults()
        assert win._inference_tab._model_combo.currentText() == "large-v3-turbo"

    def test_should_restore_defaults_for_llm_tab(self, config_manager):
        config_manager.set("llm.provider", "claude")
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        win._tabs.setCurrentIndex(2)  # LLM tab
        win._on_restore_defaults()
        assert win._llm_tab._provider_combo.currentText() == ""

    def test_should_restore_defaults_for_ui_tab(self, config_manager):
        config_manager.set("ui.quick_mode", False)
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        win._tabs.setCurrentIndex(3)  # UI tab
        win._on_restore_defaults()
        assert win._ui_tab._quick_mode_check.isChecked() is True

    def test_should_restore_defaults_for_advanced_tab(self, config_manager):
        config_manager.set("advanced.log_level", "DEBUG")
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        win._tabs.setCurrentIndex(4)  # Advanced tab
        win._on_restore_defaults()
        assert win._advanced_tab._log_level_combo.currentText() == "INFO"

    def test_should_cancel_without_saving(self, config_manager):
        config_manager.set("asr.model", "large-v3-turbo")
        win = SettingsWindow(config_manager, MagicMock(), MagicMock())
        win._inference_tab._model_combo.setCurrentText("base")
        # Reject without calling _on_accept
        win.reject()
        # Config should remain unchanged
        assert config_manager.get("asr.model") == "large-v3-turbo"


class TestApiKeyDialog:
    def test_should_accept_and_store_key(self, qapp):
        dialog = _ApiKeyDialog("openai")
        dialog._key_edit.setText("sk-my-key")
        dialog._on_accept()
        assert dialog.api_key == "sk-my-key"
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_should_return_empty_key_on_cancel(self, qapp):
        dialog = _ApiKeyDialog("claude")
        dialog._key_edit.setText("sk-my-key")
        dialog.reject()
        assert dialog.result() == QDialog.DialogCode.Rejected

    def test_should_strip_whitespace_from_key(self, qapp):
        dialog = _ApiKeyDialog("openai")
        dialog._key_edit.setText("  sk-key  ")
        dialog._on_accept()
        assert dialog.api_key == "sk-key"

    def test_should_use_password_echo_mode(self, qapp):
        dialog = _ApiKeyDialog("openai")
        assert dialog._key_edit.echoMode() == QLineEdit.EchoMode.Password
