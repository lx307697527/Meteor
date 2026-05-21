"""Tests for HistoryWindow — search, filter, re-output."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from PyQt6.QtWidgets import QApplication

from voiceime.protocols import HistoryRecord
from voiceime.ui.history_window import HistoryWindow


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.total_count = 2
    provider.search.return_value = [
        HistoryRecord(id=1, created_at="2026-05-21T10:00:00", text="你好",
                      language="zh", app_name="notepad.exe", is_polished=False),
        HistoryRecord(id=2, created_at="2026-05-21T11:00:00", text="世界",
                      language="zh", app_name="Code.exe", is_polished=True),
    ]
    return provider


@pytest.fixture
def history_window(qapp, mock_provider):
    win = HistoryWindow(mock_provider)
    yield win
    win.close()


class TestHistoryWindow:
    def test_should_populate_table_on_init(self, history_window, mock_provider):
        assert history_window._table.rowCount() == 2
        mock_provider.search.assert_called()

    def test_should_emit_re_output_signal(self, history_window, mock_provider):
        received = []
        history_window.re_output_requested.connect(lambda t: received.append(t))
        # Select first row
        history_window._table.selectRow(0)
        history_window._on_re_output()
        assert len(received) == 1
        assert received[0] == "你好"

    def test_should_not_emit_when_no_selection(self, history_window):
        received = []
        history_window.re_output_requested.connect(lambda t: received.append(t))
        history_window._table.clearSelection()
        history_window._on_re_output()
        assert len(received) == 0

    def test_should_search_with_debounce(self, history_window, mock_provider):
        history_window._search_input.setText("测试")
        # Manually trigger the timer (simulating debounce)
        history_window._do_search()
        call_args = mock_provider.search.call_args
        assert call_args.kwargs.get("query") == "测试" or "测试" in str(call_args)
