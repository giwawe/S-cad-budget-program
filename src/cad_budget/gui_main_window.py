from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class CadBudgetMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAD Budget")
        self.resize(1200, 760)
        self._page_titles = ["运行", "结果", "设置"]

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
        for label in ("DXF 文件", "报价模板", "单价表", "输出目录"):
            form_layout.addWidget(self._path_row(label))
        page.layout().addWidget(form)

        actions = QHBoxLayout()
        actions.addWidget(QPushButton("生成正式报价"))
        actions.addWidget(QPushButton("运行真实验收"))
        actions.addWidget(QPushButton("打开输出目录"))
        actions.addStretch(1)
        page.layout().addLayout(actions)

        log = QLabel("等待运行")
        log.setObjectName("runLog")
        log.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        page.layout().addWidget(log, 1)
        return page

    def _build_result_page(self) -> QWidget:
        page = self._page("结果摘要")
        stats = QHBoxLayout()
        for label in ("自动算量", "自动汇总", "模板默认", "默认推断", "异常提示", "单价匹配"):
            stats.addWidget(self._stat_card(label, "0"))
        page.layout().addLayout(stats)
        page.layout().addWidget(QLabel("复核行动"))
        page.layout().addWidget(QLabel("暂无结果"), 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = self._page("设置")
        for label in ("默认模板路径", "默认单价表路径", "默认输出目录", "DXF 默认单位"):
            page.layout().addWidget(self._path_row(label))
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

    def _path_row(self, label_text: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setFixedWidth(112)
        layout.addWidget(label)
        layout.addWidget(QLineEdit())
        layout.addWidget(QPushButton("选择"))
        return row

    def _stat_card(self, label_text: str, value: str) -> QWidget:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        layout.addWidget(value_label)
        layout.addWidget(label)
        return card
