from __future__ import annotations

from pathlib import Path

import pytest

from cad_budget.cad_adapter_models import CadUnit
from cad_budget.gui_services import (
    GuiAcceptanceRequest,
    GuiServiceError,
    run_acceptance_for_gui,
)


def test_run_acceptance_for_gui_returns_summary_and_output_files(tmp_path: Path, monkeypatch) -> None:
    dxf_path = tmp_path / "plan.dxf"
    template_path = tmp_path / "template.xlsx"
    unit_prices_path = tmp_path / "quote-unit-prices.xlsx"
    output_dir = tmp_path / "current"
    priced_output_dir = tmp_path / "priced"
    _touch(dxf_path)
    _touch(template_path)
    _touch(unit_prices_path)

    def fake_run_real_acceptance(**kwargs):
        assert kwargs["dxf_path"] == dxf_path
        assert kwargs["template_path"] == template_path
        assert kwargs["output_dir"] == output_dir
        assert kwargs["unit_prices_path"] == unit_prices_path
        assert kwargs["priced_output_dir"] == priced_output_dir
        assert kwargs["unit"] == CadUnit.MILLIMETER
        return _acceptance_summary(output_dir, priced_output_dir)

    monkeypatch.setattr("cad_budget.gui_services._run_real_acceptance", fake_run_real_acceptance)

    summary = run_acceptance_for_gui(
        GuiAcceptanceRequest(
            dxf_path=dxf_path,
            template_path=template_path,
            unit_prices_path=unit_prices_path,
            output_dir=output_dir,
            priced_output_dir=priced_output_dir,
        )
    )

    assert summary.automation_counts == {"自动算量": 53, "自动汇总": 46, "模板默认": 0}
    assert summary.review_status_counts["自动生成-默认推断"] == 38
    assert summary.action_priority_counts == {"high": 3, "medium": 3, "low": 0}
    assert summary.matched_unit_price_rows == 99
    assert summary.output_files["priced_quote"] == priced_output_dir / "quote-priced.xlsx"
    assert summary.output_files["review_checklist"] == priced_output_dir / "quote-priced-review-checklist.xlsx"


def test_run_acceptance_for_gui_reports_missing_input(tmp_path: Path) -> None:
    with pytest.raises(GuiServiceError) as exc_info:
        run_acceptance_for_gui(
            GuiAcceptanceRequest(
                dxf_path=tmp_path / "missing.dxf",
                template_path=tmp_path / "template.xlsx",
                unit_prices_path=tmp_path / "quote-unit-prices.xlsx",
                output_dir=tmp_path / "current",
                priced_output_dir=tmp_path / "priced",
            )
        )

    assert exc_info.value.stage == "input"
    assert "DXF file does not exist" in str(exc_info.value)


def test_run_acceptance_for_gui_maps_pipeline_failure(tmp_path: Path, monkeypatch) -> None:
    dxf_path = tmp_path / "plan.dxf"
    template_path = tmp_path / "template.xlsx"
    unit_prices_path = tmp_path / "quote-unit-prices.xlsx"
    _touch(dxf_path)
    _touch(template_path)
    _touch(unit_prices_path)

    def fake_run_real_acceptance(**kwargs):
        raise RuntimeError("real pipeline failed: DXF import failed")

    monkeypatch.setattr("cad_budget.gui_services._run_real_acceptance", fake_run_real_acceptance)

    with pytest.raises(GuiServiceError) as exc_info:
        run_acceptance_for_gui(
            GuiAcceptanceRequest(
                dxf_path=dxf_path,
                template_path=template_path,
                unit_prices_path=unit_prices_path,
                output_dir=tmp_path / "current",
                priced_output_dir=tmp_path / "priced",
            )
        )

    assert exc_info.value.stage == "pipeline"
    assert "DXF import failed" in str(exc_info.value)


def test_run_acceptance_for_gui_maps_priced_package_failure(tmp_path: Path, monkeypatch) -> None:
    dxf_path = tmp_path / "plan.dxf"
    template_path = tmp_path / "template.xlsx"
    unit_prices_path = tmp_path / "quote-unit-prices.xlsx"
    _touch(dxf_path)
    _touch(template_path)
    _touch(unit_prices_path)

    def fake_run_real_acceptance(**kwargs):
        raise RuntimeError("priced output check failed: Unit price mismatch")

    monkeypatch.setattr("cad_budget.gui_services._run_real_acceptance", fake_run_real_acceptance)

    with pytest.raises(GuiServiceError) as exc_info:
        run_acceptance_for_gui(
            GuiAcceptanceRequest(
                dxf_path=dxf_path,
                template_path=template_path,
                unit_prices_path=unit_prices_path,
                output_dir=tmp_path / "current",
                priced_output_dir=tmp_path / "priced",
            )
        )

    assert exc_info.value.stage == "priced_output"
    assert "Unit price mismatch" in str(exc_info.value)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def _acceptance_summary(output_dir: Path, priced_output_dir: Path):
    class Summary:
        automation_counts = {"自动算量": 53, "自动汇总": 46, "模板默认": 0}
        review_status_counts = {"自动生成-默认推断": 38, "自动生成-异常提示": 0, "按模板生成": 0}
        action_priority_counts = {"high": 3, "medium": 3, "low": 0}
        matched_unit_price_rows = 99

        def __init__(self) -> None:
            self.output_dir = output_dir
            self.priced_output_dir = priced_output_dir

    return Summary()
