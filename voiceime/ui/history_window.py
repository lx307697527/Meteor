"""HistoryWindow — search, filter, and re-output recognition history."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from voiceime.protocols import HistoryProvider, HistoryRecord


class HistoryWindow(QDialog):
    """Dialog for browsing and searching recognition history."""

    re_output_requested = pyqtSignal(str)  # emits text to re-output

    def __init__(self, provider: HistoryProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider = provider
        self.setWindowTitle("识别历史")
        self.setMinimumSize(640, 400)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._do_search()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top bar: search + app filter
        top = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索关键词...")
        self._search_input.textChanged.connect(self._on_search_changed)
        top.addWidget(self._search_input, stretch=1)

        self._app_filter = QComboBox()
        self._app_filter.addItem("全部应用")
        self._app_filter.currentIndexChanged.connect(lambda: self._do_search())
        top.addWidget(self._app_filter)

        layout.addLayout(top)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["时间", "文本", "语言", "应用", "润色"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        # Bottom bar
        bottom = QHBoxLayout()
        self._count_label = QLabel()
        bottom.addWidget(self._count_label)
        bottom.addStretch()

        self._re_output_btn = QPushButton("再次上屏")
        self._re_output_btn.clicked.connect(self._on_re_output)
        bottom.addWidget(self._re_output_btn)

        self._clear_btn = QPushButton("清空历史")
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addWidget(self._clear_btn)

        layout.addLayout(bottom)

    def _on_search_changed(self, text: str) -> None:
        self._search_timer.start(300)  # 300ms debounce

    def _do_search(self) -> None:
        query = self._search_input.text().strip()
        app = self._app_filter.currentText()
        app_filter = None if app == "全部应用" else app

        records = self._provider.search(query=query, app_filter=app_filter)

        self._table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self._table.setItem(row, 0, QTableWidgetItem(rec.created_at[:19] if rec.created_at else ""))
            self._table.setItem(row, 1, QTableWidgetItem(rec.text[:100]))
            self._table.setItem(row, 2, QTableWidgetItem(rec.language or ""))
            self._table.setItem(row, 3, QTableWidgetItem(rec.app_name or ""))
            self._table.setItem(row, 4, QTableWidgetItem("是" if rec.is_polished else "否"))
            # Store full record in first column's user data
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, rec)

        self._count_label.setText(f"共 {self._provider.total_count} 条")

    def _on_re_output(self) -> None:
        items = self._table.selectedItems()
        if not items:
            return
        row = items[0].row()
        item = self._table.item(row, 0)
        record = item.data(Qt.ItemDataRole.UserRole)
        if record and record.text:
            self.re_output_requested.emit(record.text)

    def _on_clear(self) -> None:
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self._provider.clear_all()
            self._do_search()
