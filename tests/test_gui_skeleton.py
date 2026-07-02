from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import pytest


def test_pyproject_declares_gui_optional_dependency() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    gui_dependencies = data["project"]["optional-dependencies"]["gui"]

    assert any(dependency.startswith("PySide6>=") for dependency in gui_dependencies)


def test_gui_app_module_imports_without_starting_qt() -> None:
    module = importlib.import_module("cad_budget.gui_app")

    assert hasattr(module, "main")


def test_main_window_source_wires_runtime_actions() -> None:
    source = Path("src/cad_budget/gui_main_window.py").read_text(encoding="utf-8")

    compile(source, "src/cad_budget/gui_main_window.py", "exec")
    assert "GuiRunController" in source
    assert "QFileDialog.getOpenFileName" in source
    assert "QFileDialog.getExistingDirectory" in source
    assert "QTableWidget" in source
    assert "QThread" in source
    assert "setStyleSheet" in source
    assert "subprocess.Popen" in source
    assert '"运行", "结果", "设置"' in source
    assert "cellDoubleClicked" in source
    assert "default_gui_settings" in source
    assert "load_gui_settings" in source
    assert "save_gui_settings" in source


def test_main_window_constructs_three_pages_when_pyside6_is_available(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from cad_budget.gui_main_window import CadBudgetMainWindow

    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(sys.argv[:1])
    window = CadBudgetMainWindow()

    assert app is not None
    assert window.windowTitle() == "CAD Budget"
    assert window.page_titles() == ["运行", "结果", "设置"]
