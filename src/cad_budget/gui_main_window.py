from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cad_budget.gui_controller import GuiRunController, GuiRunInputs, GuiSummaryText
from cad_budget.gui_services import GuiServiceError


class _AcceptanceWorker(QObject):
    completed = Signal(object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, inputs: GuiRunInputs) -> None:
        super().__init__()
        self._inputs = inputs

    @Slot()
    def run(self) -> None:
        try:
            summary_text = GuiRunController().run(self._inputs)
        except GuiServiceError as exc:
            self.failed.emit(exc.stage, exc.message)
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit("unexpected", str(exc))
        else:
            self.completed.emit(summary_text)
        finally:
            self.finished.emit()


class CadBudgetMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAD Budget")
        self.resize(1200, 760)
        self.setStyleSheet(_APP_STYLESHEET)
        self._page_titles = ["运行", "结果", "设置"]
        self._path_edits: dict[str, QLineEdit] = {}
        self._stat_labels: dict[str, QLabel] = {}
        self._latest_summary_text: GuiSummaryText | None = None
        self._worker_thread: QThread | None = None
        self._worker: _AcceptanceWorker | None = None

        self._navigation = QListWidget()
        self._navigation.setObjectName("mainNavigation")
        self._navigation.setFixedWidth(148)
        self._pages = QStackedWidget()
        self._pages.setObjectName("mainPages")

        for title, page in (
            ("运行", self._build_run_page()),
            ("结果", self._build_result_page()),
            ("设置", self._build_settings_page()),
        ):
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._navigation.addItem(item)
            self._pages.addWidget(page)

        self._navigation.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._navigation.setCurrentRow(0)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._navigation)
        layout.addWidget(self._pages, 1)
        self.setCentralWidget(root)

    def page_titles(self) -> list[str]:
        return list(self._page_titles)

    def _build_run_page(self) -> QWidget:
        page = self._page("项目运行")
        form = QFrame()
        form.setObjectName("runForm")
        form_layout = QVBoxLayout(form)
        form_layout.addWidget(self._path_row("dxf_path", "DXF 文件", self._choose_dxf_file))
        form_layout.addWidget(self._path_row("template_path", "报价模板", self._choose_template_file))
        form_layout.addWidget(self._path_row("unit_prices_path", "单价表", self._choose_unit_prices_file))
        form_layout.addWidget(self._path_row("output_root", "输出目录", self._choose_output_root))
        page.layout().addWidget(form)

        actions = QHBoxLayout()
        self._run_button = QPushButton("运行真实验收")
        self._run_button.setObjectName("runAcceptanceButton")
        self._run_button.clicked.connect(self._run_acceptance)
        actions.addWidget(self._run_button)

        self._open_output_button = QPushButton("打开输出目录")
        self._open_output_button.setObjectName("openOutputButton")
        self._open_output_button.clicked.connect(self._open_output_dir)
        actions.addWidget(self._open_output_button)
        actions.addStretch(1)
        page.layout().addLayout(actions)

        self._run_log = QLabel("等待运行")
        self._run_log.setObjectName("runLog")
        self._run_log.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        page.layout().addWidget(self._run_log, 1)
        return page

    def _build_result_page(self) -> QWidget:
        page = self._page("结果摘要")
        stats = QHBoxLayout()
        for label in ("自动算量", "自动汇总", "模板默认", "默认推断", "异常提示", "单价匹配"):
            stats.addWidget(self._stat_card(label, "0"))
        page.layout().addLayout(stats)
        page.layout().addWidget(QLabel("复核行动"))
        self._result_details = QLabel("暂无结果")
        self._result_details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        page.layout().addWidget(self._result_details)

        page.layout().addWidget(QLabel("输出文件"))
        self._output_files_table = QTableWidget(0, 2)
        self._output_files_table.setObjectName("outputFilesTable")
        self._output_files_table.setHorizontalHeaderLabels(["文件", "路径"])
        self._output_files_table.horizontalHeader().setStretchLastSection(True)
        self._output_files_table.verticalHeader().setVisible(False)
        self._output_files_table.setAlternatingRowColors(True)
        self._output_files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        page.layout().addWidget(self._output_files_table, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = self._page("设置")
        for label in ("默认模板路径", "默认单价表路径", "默认输出目录", "DXF 默认单位"):
            page.layout().addWidget(self._path_row("", label, None))
        page.layout().addStretch(1)
        return page

    def _page(self, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        return page

    def _path_row(self, key: str, label_text: str, chooser) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setFixedWidth(112)
        edit = QLineEdit()
        if key:
            edit.setObjectName(key)
            self._path_edits[key] = edit
        button = QPushButton("选择")
        if chooser is not None:
            button.clicked.connect(chooser)
        else:
            button.setEnabled(False)
        layout.addWidget(label)
        layout.addWidget(edit)
        layout.addWidget(button)
        return row

    def _stat_card(self, label_text: str, value: str) -> QWidget:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        value_label = QLabel(value)
        value_label.setObjectName(f"{label_text}Value")
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        self._stat_labels[label_text] = value_label
        layout.addWidget(value_label)
        layout.addWidget(label)
        return card

    @Slot()
    def _choose_dxf_file(self) -> None:
        self._choose_file("dxf_path", "选择 DXF 文件", "DXF files (*.dxf);;All files (*)")

    @Slot()
    def _choose_template_file(self) -> None:
        self._choose_file("template_path", "选择报价模板", "Excel files (*.xlsx);;All files (*)")

    @Slot()
    def _choose_unit_prices_file(self) -> None:
        self._choose_file("unit_prices_path", "选择单价表", "Excel files (*.xlsx);;All files (*)")

    @Slot()
    def _choose_output_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self._path_edits["output_root"].setText(directory)

    def _choose_file(self, key: str, title: str, file_filter: str) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if filename:
            self._path_edits[key].setText(filename)

    @Slot()
    def _run_acceptance(self) -> None:
        try:
            inputs = self._build_inputs()
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        self._run_button.setEnabled(False)
        self._run_log.setText("正在运行真实验收...")
        self._worker_thread = QThread(self)
        self._worker = _AcceptanceWorker(inputs)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.completed.connect(self._handle_run_completed)
        self._worker.failed.connect(self._handle_run_failed)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._clear_worker)
        self._worker_thread.start()

    def _build_inputs(self) -> GuiRunInputs:
        values = {key: edit.text().strip() for key, edit in self._path_edits.items()}
        missing = [label for key, label in _INPUT_LABELS.items() if not values.get(key)]
        if missing:
            raise ValueError("请先选择：" + "、".join(missing))
        return GuiRunInputs(
            dxf_path=Path(values["dxf_path"]),
            template_path=Path(values["template_path"]),
            unit_prices_path=Path(values["unit_prices_path"]),
            output_root=Path(values["output_root"]),
        )

    @Slot(object)
    def _handle_run_completed(self, summary_text: GuiSummaryText) -> None:
        self._latest_summary_text = summary_text
        text = "\n".join(summary_text.lines)
        self._run_log.setText(text)
        self._result_details.setText(text)
        self._render_output_files(summary_text)
        for line in summary_text.lines[1:]:
            label, _, value = line.partition(": ")
            stat_label = "单价匹配" if label == "单价匹配行" else label
            if stat_label in self._stat_labels:
                self._stat_labels[stat_label].setText(value)
        self._run_button.setEnabled(True)
        self._pages.setCurrentIndex(1)

    def _render_output_files(self, summary_text: GuiSummaryText) -> None:
        self._output_files_table.setRowCount(len(summary_text.output_files))
        for row, (label, path) in enumerate(summary_text.output_files):
            self._output_files_table.setItem(row, 0, QTableWidgetItem(label))
            self._output_files_table.setItem(row, 1, QTableWidgetItem(str(path)))

    @Slot(str, str)
    def _handle_run_failed(self, stage: str, message: str) -> None:
        text = f"运行失败 ({stage}): {message}"
        self._run_log.setText(text)
        self._result_details.setText(text)
        self._run_button.setEnabled(True)
        QMessageBox.warning(self, "运行失败", text)

    @Slot()
    def _clear_worker(self) -> None:
        self._worker_thread = None
        self._worker = None

    @Slot()
    def _open_output_dir(self) -> None:
        directory = self._latest_summary_text.priced_output_dir if self._latest_summary_text else self._selected_output_root()
        if directory is None:
            self._show_input_error("请先选择输出目录")
            return
        subprocess.Popen(["explorer", str(directory)])

    def _selected_output_root(self) -> Path | None:
        text = self._path_edits.get("output_root", QLineEdit()).text().strip()
        return Path(text) if text else None

    def _show_input_error(self, message: str) -> None:
        self._run_log.setText(message)
        QMessageBox.warning(self, "输入不完整", message)


_INPUT_LABELS = {
    "dxf_path": "DXF 文件",
    "template_path": "报价模板",
    "unit_prices_path": "单价表",
    "output_root": "输出目录",
}


_APP_STYLESHEET = """
QMainWindow {
    background: #f6f7f9;
}
QListWidget#mainNavigation {
    background: #202733;
    border: 0;
    color: #e8edf4;
    font-size: 15px;
    padding-top: 16px;
}
QListWidget#mainNavigation::item {
    min-height: 44px;
    border-left: 3px solid transparent;
}
QListWidget#mainNavigation::item:selected {
    background: #2f7d6d;
    border-left-color: #f2c94c;
}
QLabel#pageHeading {
    color: #1f2933;
    font-size: 22px;
    font-weight: 600;
}
QFrame#runForm,
QFrame#statCard {
    background: #ffffff;
    border: 1px solid #d8dee8;
    border-radius: 6px;
}
QLineEdit {
    background: #ffffff;
    border: 1px solid #c8d0dc;
    border-radius: 4px;
    min-height: 30px;
    padding: 0 8px;
}
QPushButton {
    background: #2f7d6d;
    border: 0;
    border-radius: 4px;
    color: #ffffff;
    min-height: 32px;
    padding: 0 14px;
}
QPushButton:disabled {
    background: #a8b4c2;
}
QLabel#runLog {
    background: #ffffff;
    border: 1px solid #d8dee8;
    border-radius: 6px;
    padding: 12px;
}
QTableWidget#outputFilesTable {
    background: #ffffff;
    alternate-background-color: #f0f3f7;
    border: 1px solid #d8dee8;
    gridline-color: #e4e8ef;
}
"""
