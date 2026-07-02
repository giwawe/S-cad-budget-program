from __future__ import annotations

from pathlib import Path

import pytest

from cad_budget.cad_adapter_models import CadUnit
from cad_budget.gui_controller import GuiRunController, GuiRunInputs
from cad_budget.gui_services import GuiRunSummary, GuiServiceError


AUTO_TAKEOFF = "\u81ea\u52a8\u7b97\u91cf"
AUTO_SUMMARY = "\u81ea\u52a8\u6c47\u603b"
TEMPLATE_DEFAULT = "\u6a21\u677f\u9ed8\u8ba4"
AUTO_DEFAULT_INFERRED = "\u81ea\u52a8\u751f\u6210-\u9ed8\u8ba4\u63a8\u65ad"
AUTO_EXCEPTION_HINT = "\u81ea\u52a8\u751f\u6210-\u5f02\u5e38\u63d0\u793a"


def test_gui_run_inputs_build_acceptance_request_from_output_root(tmp_path: Path) -> None:
    inputs = GuiRunInputs(
        dxf_path=tmp_path / "10.dxf",
        template_path=tmp_path / "template.xlsx",
        unit_prices_path=tmp_path / "quote-unit-prices.xlsx",
        output_root=tmp_path / "gui-output",
    )

    request = inputs.to_acceptance_request()

    assert request.dxf_path == tmp_path / "10.dxf"
    assert request.template_path == tmp_path / "template.xlsx"
    assert request.unit_prices_path == tmp_path / "quote-unit-prices.xlsx"
    assert request.output_dir == tmp_path / "gui-output" / "cad-import-10-real-template-current"
    assert request.priced_output_dir == tmp_path / "gui-output" / "cad-import-10-real-template-priced-command"
    assert request.unit == CadUnit.MILLIMETER


def test_gui_run_controller_runs_acceptance_and_formats_summary(tmp_path: Path) -> None:
    calls = []

    def fake_runner(request):
        calls.append(request)
        return GuiRunSummary(
            output_dir=request.output_dir,
            priced_output_dir=request.priced_output_dir,
            automation_counts={AUTO_TAKEOFF: 53, AUTO_SUMMARY: 46, TEMPLATE_DEFAULT: 0},
            review_status_counts={AUTO_DEFAULT_INFERRED: 38, AUTO_EXCEPTION_HINT: 0},
            action_priority_counts={"high": 3, "medium": 3, "low": 0},
            matched_unit_price_rows=99,
            output_files={"priced_quote": request.priced_output_dir / "quote-priced.xlsx"},
        )

    controller = GuiRunController(runner=fake_runner)
    summary_text = controller.run(
        GuiRunInputs(
            dxf_path=tmp_path / "10.dxf",
            template_path=tmp_path / "template.xlsx",
            unit_prices_path=tmp_path / "quote-unit-prices.xlsx",
            output_root=tmp_path / "gui-output",
        )
    )

    assert len(calls) == 1
    assert controller.latest_summary is not None
    assert summary_text.lines == [
        "\u771f\u5b9e\u9a8c\u6536\u5b8c\u6210",
        "\u81ea\u52a8\u7b97\u91cf: 53",
        "\u81ea\u52a8\u6c47\u603b: 46",
        "\u6a21\u677f\u9ed8\u8ba4: 0",
        "\u9ed8\u8ba4\u63a8\u65ad: 38",
        "\u5f02\u5e38\u63d0\u793a: 0",
        "\u9ad8\u4f18\u5148\u7ea7\u590d\u6838: 3",
        "\u4e2d\u4f18\u5148\u7ea7\u590d\u6838: 3",
        "\u5355\u4ef7\u5339\u914d\u884c: 99",
    ]
    assert summary_text.output_dir == tmp_path / "gui-output" / "cad-import-10-real-template-current"
    assert summary_text.priced_output_dir == tmp_path / "gui-output" / "cad-import-10-real-template-priced-command"
    assert summary_text.output_files == [
        ("\u6b63\u5f0f\u62a5\u4ef7\u8868", tmp_path / "gui-output" / "cad-import-10-real-template-priced-command" / "quote-priced.xlsx"),
    ]


def test_gui_run_controller_formats_service_errors(tmp_path: Path) -> None:
    def failing_runner(request):
        raise GuiServiceError("pipeline", "DXF import failed")

    controller = GuiRunController(runner=failing_runner)

    with pytest.raises(GuiServiceError) as exc_info:
        controller.run(
            GuiRunInputs(
                dxf_path=tmp_path / "10.dxf",
                template_path=tmp_path / "template.xlsx",
                unit_prices_path=tmp_path / "quote-unit-prices.xlsx",
                output_root=tmp_path / "gui-output",
            )
        )

    assert exc_info.value.stage == "pipeline"
    assert controller.latest_error == "pipeline: DXF import failed"
