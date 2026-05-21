"""HotwordWindow — manage hotword entries with CRUD and CSV import/export."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
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

from voiceime.hotword.repository import HotwordRepo


class _HotwordEditDialog(QDialog):
    """Dialog for adding or editing a hotword entry."""

    def __init__(self, parent: QWidget | None = None, trigger: str = "",
                 replace: str = "", case_sensitive: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑热词" if trigger else "添加热词")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)

        self._trigger_input = QLineEdit(trigger)
        layout.addRow("触发词：", self._trigger_input)

        self._replace_input = QLineEdit(replace)
        layout.addRow("替换为：", self._replace_input)

        self._case_check = QCheckBox("区分大小写")
        self._case_check.setChecked(case_sensitive)
        layout.addRow(self._case_check)

        btns = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)

    @property
    def trigger(self) -> str:
        return self._trigger_input.text().strip()

    @property
    def replace(self) -> str:
        return self._replace_input.text().strip()

    @property
    def case_sensitive(self) -> bool:
        return self._case_check.isChecked()


class HotwordWindow(QDialog):
    """Dialog for managing hotword entries."""

    def __init__(self, repo: HotwordRepo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setWindowTitle("热词管理")
        self.setMinimumSize(560, 400)
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top bar
        top = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索热词...")
        self._search_input.textChanged.connect(self._on_search_changed)
        top.addWidget(self._search_input, stretch=1)

        self._add_btn = QPushButton("添加")
        self._add_btn.clicked.connect(self._on_add)
        top.addWidget(self._add_btn)

        self._import_btn = QPushButton("导入 CSV")
        self._import_btn.clicked.connect(self._on_import_csv)
        top.addWidget(self._import_btn)

        self._export_btn = QPushButton("导出 CSV")
        self._export_btn.clicked.connect(self._on_export_csv)
        top.addWidget(self._export_btn)

        layout.addLayout(top)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["触发词", "替换为", "区分大小写"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._table)

    def _refresh_table(self) -> None:
        entries = self._repo.list_all()
        query = self._search_input.text().strip().lower()

        filtered = entries
        if query:
            filtered = [
                e for e in entries
                if query in e["trigger"].lower() or query in e["replace"].lower()
            ]

        self._table.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            self._table.setItem(row, 0, QTableWidgetItem(entry["trigger"]))
            self._table.setItem(row, 1, QTableWidgetItem(entry["replace"]))
            self._table.setItem(row, 2, QTableWidgetItem(
                "是" if entry.get("case_sensitive") else "否"
            ))
            # Store index for edit/delete
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entries.index(entry))

    def _on_search_changed(self) -> None:
        self._refresh_table()

    def _on_add(self) -> None:
        dlg = _HotwordEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.trigger and dlg.replace:
            self._repo.add(dlg.trigger, dlg.replace, dlg.case_sensitive)
            self._refresh_table()

    def _on_context_menu(self, pos) -> None:
        item = self._table.itemAt(pos)
        if not item:
            return
        row = item.row()
        idx = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == edit_action:
            entries = self._repo.list_all()
            if 0 <= idx < len(entries):
                e = entries[idx]
                dlg = _HotwordEditDialog(
                    self, e["trigger"], e["replace"], e.get("case_sensitive", False)
                )
                if dlg.exec() == QDialog.DialogCode.Accepted and dlg.trigger and dlg.replace:
                    self._repo.update(idx, dlg.trigger, dlg.replace, dlg.case_sensitive)
                    self._refresh_table()
        elif action == delete_action:
            if self._repo.delete(idx):
                self._refresh_table()

    def _on_import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入热词 CSV", "", "CSV 文件 (*.csv)"
        )
        if path:
            count = self._repo.import_csv(Path(path))
            self._refresh_table()
            QMessageBox.information(self, "导入完成", f"成功导入 {count} 条热词")

    def _on_export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出热词 CSV", "hotwords.csv", "CSV 文件 (*.csv)"
        )
        if path:
            self._repo.export_csv(Path(path))
            QMessageBox.information(self, "导出完成", "热词已导出")
