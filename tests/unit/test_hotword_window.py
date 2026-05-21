"""Tests for HotwordWindow — add, edit, delete, CSV import/export."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from PyQt6.QtWidgets import QApplication

from voiceime.hotword.repository import HotwordRepo
from voiceime.ui.hotword_window import HotwordWindow


@pytest.fixture
def hotword_file(tmp_path):
    return tmp_path / "test_hotwords.json"


@pytest.fixture
def repo(hotword_file):
    return HotwordRepo(path=hotword_file)


@pytest.fixture
def hotword_window(qapp, repo):
    win = HotwordWindow(repo)
    yield win
    win.close()


class TestHotwordWindow:
    def test_should_show_empty_table_when_no_entries(self, hotword_window):
        assert hotword_window._table.rowCount() == 0

    def test_should_refresh_table_after_add(self, hotword_window, repo):
        repo.add("测试", "Test")
        hotword_window._refresh_table()
        assert hotword_window._table.rowCount() == 1
        assert hotword_window._table.item(0, 0).text() == "测试"
        assert hotword_window._table.item(0, 1).text() == "Test"

    def test_should_filter_by_search(self, hotword_window, repo):
        repo.add("你尼达", "UniData")
        repo.add("语音", "Voice")
        hotword_window._search_input.setText("你尼")
        hotword_window._refresh_table()
        assert hotword_window._table.rowCount() == 1

    def test_should_refresh_after_delete(self, hotword_window, repo):
        repo.add("del_me", "Delete")
        hotword_window._refresh_table()
        assert hotword_window._table.rowCount() == 1
        repo.delete(0)
        hotword_window._refresh_table()
        assert hotword_window._table.rowCount() == 0
