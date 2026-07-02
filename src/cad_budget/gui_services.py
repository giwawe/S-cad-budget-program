from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cad_budget.cad_adapter_models import CadUnit


class GuiServiceError(Exception):
    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class GuiAcceptanceRequest:
    dxf_path: Path
    template_path: Path
    unit_prices_path: Path
    output_dir: Path
    priced_output_dir: Path
    unit: CadUnit = CadUnit.MILLIMETER
    rules_path: Path | None = None


@dataclass(frozen=True)
class GuiRunSummary:
    output_dir: Path
    priced_output_dir: Path
    automation_counts: dict[str, int]
    review_status_counts: dict[str, int]
    action_priority_counts: dict[str, int]
    matched_unit_price_rows: int
    output_files: dict[str, Path] = field(default_factory=dict)


def run_acceptance_for_gui(request: GuiAcceptanceRequest) -> GuiRunSummary:
    _validate_request(request)
    try:
        summary = _run_real_acceptance(
            dxf_path=request.dxf_path,
            template_path=request.template_path,
            output_dir=request.output_dir,
            unit_prices_path=request.unit_prices_path,
            priced_output_dir=request.priced_output_dir,
            unit=request.unit,
            rules_path=request.rules_path,
        )
    except Exception as exc:
        raise _to_gui_error(exc) from exc

    return GuiRunSummary(
        output_dir=summary.output_dir,
        priced_output_dir=summary.priced_output_dir,
        automation_counts=dict(summary.automation_counts),
        review_status_counts=dict(summary.review_status_counts),
        action_priority_counts=dict(summary.action_priority_counts),
        matched_unit_price_rows=int(summary.matched_unit_price_rows),
        output_files=_output_files(summary.output_dir, summary.priced_output_dir),
    )


def _validate_request(request: GuiAcceptanceRequest) -> None:
    _require_file(request.dxf_path, "DXF file")
    _require_file(request.template_path, "quote template")
    _require_file(request.unit_prices_path, "unit price workbook")
    if request.rules_path is not None:
        _require_file(request.rules_path, "quote rules file")


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise GuiServiceError("input", f"{label} does not exist: {path}")
    if not path.is_file():
        raise GuiServiceError("input", f"{label} is not a file: {path}")


def _to_gui_error(exc: Exception) -> GuiServiceError:
    message = str(exc)
    if message.startswith("real pipeline failed:"):
        return GuiServiceError("pipeline", message.removeprefix("real pipeline failed:").strip())
    if message.startswith("key result assertions failed:"):
        return GuiServiceError("key_results", message.removeprefix("key result assertions failed:").strip())
    if message.startswith("priced output check failed:"):
        return GuiServiceError("priced_output", message.removeprefix("priced output check failed:").strip())
    return GuiServiceError("acceptance", message)


def _output_files(output_dir: Path, priced_output_dir: Path) -> dict[str, Path]:
    return {
        "project_json": output_dir / "project.json",
        "result_json": output_dir / "result.json",
        "result_excel": output_dir / "result.xlsx",
        "quote": output_dir / "quote.xlsx",
        "quote_review_markdown": output_dir / "quote-review.md",
        "quote_review_json": output_dir / "quote-review.json",
        "quote_review_checklist": output_dir / "quote-review-checklist.xlsx",
        "summary_json": output_dir / "summary.json",
        "priced_quote": priced_output_dir / "quote-priced.xlsx",
        "priced_review_markdown": priced_output_dir / "quote-priced-review.md",
        "priced_review_json": priced_output_dir / "quote-priced-review.json",
        "review_checklist": priced_output_dir / "quote-priced-review-checklist.xlsx",
    }


def _run_real_acceptance(**kwargs):
    from scripts.run_real_acceptance import run_real_acceptance

    return run_real_acceptance(**kwargs)
