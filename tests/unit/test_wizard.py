"""Tests for FirstRunWizard — mic check, model download, hotkey confirm pages."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from PyQt6.QtWidgets import QApplication, QWizard, QWizardPage

from voiceime.ui.wizard import (
    FirstRunWizard,
    _HotkeyConfirmPage,
    _MicCheckPage,
    _ModelDownloadPage,
)


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    """All wizard tests need a QApplication."""


@pytest.fixture
def wizard(config_manager, qapp):
    model_mgr = MagicMock(spec=Path)
    wizard = FirstRunWizard(config_manager, model_mgr)
    yield wizard
    wizard.close()


class TestMicCheckPage:
    def test_should_show_loading_message_on_init(self):
        page = _MicCheckPage()
        assert "正在检测" in page._info_label.text()

    @patch("voiceime.ui.wizard.list_devices")
    def test_should_show_devices_when_found(self, mock_list_devices):
        mock_list_devices.return_value = [
            MagicMock(name="Mic 1", is_default=True),
            MagicMock(name="Mic 2", is_default=False),
        ]
        page = _MicCheckPage()
        page.initializePage()
        assert "检测到 2 个麦克风设备" in page._info_label.text()
        assert "Mic 1" in page._info_label.text()
        assert page.isComplete() is True

    @patch("voiceime.ui.wizard.list_devices")
    def test_should_show_error_when_no_devices(self, mock_list_devices):
        mock_list_devices.return_value = []
        page = _MicCheckPage()
        page.initializePage()
        assert "未检测到麦克风设备" in page._info_label.text()
        assert page.isComplete() is False

    @patch("voiceime.ui.wizard.list_devices")
    def test_should_mark_complete_when_devices_found(self, mock_list_devices):
        mock_list_devices.return_value = [MagicMock(name="Mic 1", is_default=True)]
        page = _MicCheckPage()
        page.initializePage()
        assert page.isComplete() is True


class TestModelDownloadPage:
    def test_should_show_ready_message_on_init(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        assert "准备下载" in page._status.text()

    def test_should_start_download_on_show(self):
        model_mgr = MagicMock()
        model_mgr.download_progress = None
        config = MagicMock()
        config.get.return_value = "large-v3-turbo"
        page = _ModelDownloadPage(model_mgr, config)
        # Simulate showEvent
        page._start_download()
        assert page._started is True

    def test_should_poll_progress_when_downloading(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        page._success = False

        progress = MagicMock()
        progress.total_bytes = 1000
        progress.downloaded_bytes = 500
        progress.speed_bps = 50 * 1024 * 1024  # 50 MB/s
        model_mgr.download_progress = progress

        page._poll_progress()
        assert page._progress.value() == 50
        assert "50.0 MB/s" in page._status.text()

    def test_should_show_100_percent_on_complete(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        page.download_finished.emit(True, "")
        assert page._success is True
        assert page._progress.value() == 100
        assert "完成" in page._status.text()

    def test_should_show_error_on_failure(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        page.download_finished.emit(False, "network error")
        assert page._success is False
        assert "失败" in page._status.text()

    def test_should_not_start_download_twice(self):
        model_mgr = MagicMock()
        model_mgr.download_progress = None  # No progress data to avoid _poll_progress crash
        config = MagicMock()
        config.get.return_value = "large-v3-turbo"
        page = _ModelDownloadPage(model_mgr, config)
        page._start_download()
        page._start_download()
        assert page._started is True

    def test_should_validate_success_before_proceeding(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        assert page.validatePage() is False
        page._success = True
        assert page.validatePage() is True

    def test_should_be_incomplete_when_not_successful(self):
        model_mgr = MagicMock()
        config = MagicMock()
        page = _ModelDownloadPage(model_mgr, config)
        assert page.isComplete() is False


class TestHotkeyConfirmPage:
    def test_should_show_caps_lock_info_by_default(self, config_manager):
        config_manager.set("hotkey", "caps_lock")
        page = _HotkeyConfirmPage(config_manager)
        assert "Caps Lock" in page._info_label.text()

    def test_should_show_custom_hotkey_when_configured(self, config_manager):
        config_manager.set("hotkey", "f1")
        page = _HotkeyConfirmPage(config_manager)
        assert "f1" in page._info_label.text()
        assert "Caps Lock" not in page._info_label.text()

    def test_should_show_usage_instructions(self, config_manager):
        config_manager.set("hotkey", "caps_lock")
        page = _HotkeyConfirmPage(config_manager)
        text = page._info_label.text()
        assert "按住" in text
        assert "松开" in text
        assert "等待识别" in text


class TestFirstRunWizard:
    def test_should_have_three_pages(self, wizard):
        assert len(wizard.pageIds()) == 3

    def test_should_have_mic_check_as_first_page(self, wizard):
        page1 = wizard.page(0)
        assert isinstance(page1, _MicCheckPage)
        assert page1.title() == "麦克风检测"

    def test_should_have_model_download_as_second_page(self, wizard):
        page2 = wizard.page(1)
        assert isinstance(page2, _ModelDownloadPage)
        assert page2.title() == "下载语音模型"

    def test_should_have_hotkey_confirm_as_third_page(self, wizard):
        page3 = wizard.page(2)
        assert isinstance(page3, _HotkeyConfirmPage)
        assert page3.title() == "快捷键说明"

    def test_should_have_modern_style(self, wizard):
        from PyQt6.QtWidgets import QWizard
        assert wizard.wizardStyle() == QWizard.WizardStyle.ModernStyle

    def test_should_not_have_back_button_on_start(self, wizard):
        assert wizard.testOption(QWizard.WizardOption.NoBackButtonOnStartPage)

    def test_should_set_window_title(self, wizard):
        assert wizard.windowTitle() == "VoiceIME 首次设置"

    def test_should_set_minimum_size(self, wizard):
        assert wizard.minimumSize().width() >= 560
        assert wizard.minimumSize().height() >= 400

    def test_should_mark_first_run_complete(self, config_manager):
        model_mgr = MagicMock()
        wizard = FirstRunWizard(config_manager, model_mgr)
        wizard.mark_complete(config_manager)
        assert config_manager.get("first_run_complete") is True
        wizard.close()
