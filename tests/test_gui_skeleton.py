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
    assert "setColumnWidth(0, 180)" in source
    assert "default_gui_settings" in source
    assert "load_gui_settings" in source
    assert "save_gui_settings" in source
    assert "Microsoft YaHei UI" in source


def test_main_window_constructs_three_pages_when_pyside6_is_available(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from cad_budget.gui_main_window import CadBudgetMainWindow

    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(sys.argv[:1])
    window = CadBudgetMainWindow()

    assert app is not None
    assert window.windowTitle() == "CAD Budget"
    assert window.page_titles() == ["运行", "结果", "设置"]


def test_main_window_saves_settings_and_reloads_from_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from cad_budget.gui_main_window import CadBudgetMainWindow

    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(sys.argv[:1])
    config_path = tmp_path / "gui-settings.json"
    first = CadBudgetMainWindow(settings_path=config_path)
    first._settings_edits["dxf_path"].setText(str(tmp_path / "a.dxf"))
    first._settings_edits["template_path"].setText(str(tmp_path / "template.xlsx"))
    first._settings_edits["unit_prices_path"].setText(str(tmp_path / "prices.xlsx"))
    first._settings_edits["output_root"].setText(str(tmp_path / "out"))
    first._save_settings()
    first.close()

    second = CadBudgetMainWindow(settings_path=config_path)

    assert app is not None
    assert second._path_edits["dxf_path"].text() == str(tmp_path / "a.dxf")
    assert second._path_edits["template_path"].text() == str(tmp_path / "template.xlsx")
    assert second._path_edits["unit_prices_path"].text() == str(tmp_path / "prices.xlsx")
    assert second._path_edits["output_root"].text() == str(tmp_path / "out")


def test_main_window_double_click_opens_selected_output_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    from cad_budget.gui_controller import GuiSummaryText
    from cad_budget.gui_main_window import CadBudgetMainWindow

    calls = []
    monkeypatch.setattr("cad_budget.gui_main_window.subprocess.Popen", lambda args: calls.append(args))
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(sys.argv[:1])
    window = CadBudgetMainWindow(settings_path=tmp_path / "gui-settings.json")
    target = tmp_path / "quote-priced.xlsx"
    window._latest_summary_text = GuiSummaryText(
        lines=[],
        output_dir=tmp_path / "current",
        priced_output_dir=tmp_path / "priced",
        output_files=[("正式报价表", target)],
    )
    window._render_output_files(window._latest_summary_text)

    window._open_output_file(0, 0)

    assert app is not None
    assert calls == [["explorer", str(target)]]
