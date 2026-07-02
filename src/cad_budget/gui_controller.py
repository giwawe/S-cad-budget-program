from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cad_budget.cad_adapter_models import CadUnit
from cad_budget.gui_services import GuiAcceptanceRequest, GuiRunSummary, GuiServiceError, run_acceptance_for_gui


CURRENT_OUTPUT_DIR_NAME = "cad-import-10-real-template-current"
PRICED_OUTPUT_DIR_NAME = "cad-import-10-real-template-priced-command"

TEXT_ACCEPTANCE_COMPLETE = "\u771f\u5b9e\u9a8c\u6536\u5b8c\u6210"
TEXT_AUTO_TAKEOFF = "\u81ea\u52a8\u7b97\u91cf"
TEXT_AUTO_SUMMARY = "\u81ea\u52a8\u6c47\u603b"
TEXT_TEMPLATE_DEFAULT = "\u6a21\u677f\u9ed8\u8ba4"
TEXT_DEFAULT_INFERRED = "\u9ed8\u8ba4\u63a8\u65ad"
TEXT_EXCEPTION_HINT = "\u5f02\u5e38\u63d0\u793a"
TEXT_AUTO_DEFAULT_INFERRED = "\u81ea\u52a8\u751f\u6210-\u9ed8\u8ba4\u63a8\u65ad"
TEXT_AUTO_EXCEPTION_HINT = "\u81ea\u52a8\u751f\u6210-\u5f02\u5e38\u63d0\u793a"
TEXT_HIGH_REVIEW = "\u9ad8\u4f18\u5148\u7ea7\u590d\u6838"
TEXT_MEDIUM_REVIEW = "\u4e2d\u4f18\u5148\u7ea7\u590d\u6838"
TEXT_UNIT_PRICE_MATCHED = "\u5355\u4ef7\u5339\u914d\u884c"
TEXT_RUN_FAILED = "\u8fd0\u884c\u5931\u8d25"
TEXT_STAGE_INPUT = "\u8f93\u5165\u6587\u4ef6\u68c0\u67e5"
TEXT_STAGE_PIPELINE = "CAD \u5bfc\u5165/\u751f\u6210\u6d41\u7a0b"
TEXT_STAGE_KEY_RESULTS = "\u5173\u952e\u4e1a\u52a1\u7ed3\u679c\u65ad\u8a00"
TEXT_STAGE_PRICED_OUTPUT = "\u6b63\u5f0f\u62a5\u4ef7\u5305\u6821\u9a8c"
TEXT_STAGE_ACCEPTANCE = "\u771f\u5b9e\u9a8c\u6536"
TEXT_STAGE_UNEXPECTED = "\u672a\u9884\u671f\u9519\u8bef"
TEXT_PRICED_QUOTE = "\u6b63\u5f0f\u62a5\u4ef7\u8868"
TEXT_PRICED_REVIEW = "\u6b63\u5f0f\u62a5\u4ef7\u590d\u6838\u62a5\u544a"
TEXT_PRICED_REVIEW_JSON = "\u590d\u6838\u6570\u636e"
TEXT_REVIEW_CHECKLIST = "\u590d\u6838\u6e05\u5355"
TEXT_SUMMARY_JSON = "\u8fd0\u884c\u6458\u8981"

OUTPUT_FILE_LABELS = {
    "priced_quote": TEXT_PRICED_QUOTE,
    "priced_review_markdown": TEXT_PRICED_REVIEW,
    "priced_review_json": TEXT_PRICED_REVIEW_JSON,
    "review_checklist": TEXT_REVIEW_CHECKLIST,
    "summary_json": TEXT_SUMMARY_JSON,
}

STAGE_LABELS = {
    "input": TEXT_STAGE_INPUT,
    "pipeline": TEXT_STAGE_PIPELINE,
    "key_results": TEXT_STAGE_KEY_RESULTS,
    "priced_output": TEXT_STAGE_PRICED_OUTPUT,
    "acceptance": TEXT_STAGE_ACCEPTANCE,
    "unexpected": TEXT_STAGE_UNEXPECTED,
}


@dataclass(frozen=True)
class GuiRunInputs:
    dxf_path: Path
    template_path: Path
    unit_prices_path: Path
    output_root: Path
    unit: CadUnit = CadUnit.MILLIMETER
    rules_path: Path | None = None

    def to_acceptance_request(self) -> GuiAcceptanceRequest:
        return GuiAcceptanceRequest(
            dxf_path=self.dxf_path,
            template_path=self.template_path,
            unit_prices_path=self.unit_prices_path,
            output_dir=self.output_root / CURRENT_OUTPUT_DIR_NAME,
            priced_output_dir=self.output_root / PRICED_OUTPUT_DIR_NAME,
            unit=self.unit,
            rules_path=self.rules_path,
        )


@dataclass(frozen=True)
class GuiSummaryText:
    lines: list[str]
    output_dir: Path
    priced_output_dir: Path
    output_files: list[tuple[str, Path]]


class GuiRunController:
    def __init__(self, runner: Callable[[GuiAcceptanceRequest], GuiRunSummary] = run_acceptance_for_gui) -> None:
        self._runner = runner
        self.latest_summary: GuiRunSummary | None = None
        self.latest_error: str | None = None

    def run(self, inputs: GuiRunInputs) -> GuiSummaryText:
        self.latest_error = None
        try:
            summary = self._runner(inputs.to_acceptance_request())
        except GuiServiceError as exc:
            self.latest_summary = None
            self.latest_error = f"{exc.stage}: {exc.message}"
            raise

        self.latest_summary = summary
        return _format_summary(summary)


def _format_summary(summary: GuiRunSummary) -> GuiSummaryText:
    lines = [
        TEXT_ACCEPTANCE_COMPLETE,
        f"{TEXT_AUTO_TAKEOFF}: {summary.automation_counts.get(TEXT_AUTO_TAKEOFF, 0)}",
        f"{TEXT_AUTO_SUMMARY}: {summary.automation_counts.get(TEXT_AUTO_SUMMARY, 0)}",
        f"{TEXT_TEMPLATE_DEFAULT}: {summary.automation_counts.get(TEXT_TEMPLATE_DEFAULT, 0)}",
        f"{TEXT_DEFAULT_INFERRED}: {summary.review_status_counts.get(TEXT_AUTO_DEFAULT_INFERRED, 0)}",
        f"{TEXT_EXCEPTION_HINT}: {summary.review_status_counts.get(TEXT_AUTO_EXCEPTION_HINT, 0)}",
        f"{TEXT_HIGH_REVIEW}: {summary.action_priority_counts.get('high', 0)}",
        f"{TEXT_MEDIUM_REVIEW}: {summary.action_priority_counts.get('medium', 0)}",
        f"{TEXT_UNIT_PRICE_MATCHED}: {summary.matched_unit_price_rows}",
    ]
    return GuiSummaryText(
        lines=lines,
        output_dir=summary.output_dir,
        priced_output_dir=summary.priced_output_dir,
        output_files=_format_output_files(summary.output_files),
    )


def _format_output_files(output_files: dict[str, Path]) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for key, label in OUTPUT_FILE_LABELS.items():
        path = output_files.get(key)
        if path is not None:
            rows.append((label, path))
    return rows


def format_stage_error(stage: str, message: str) -> str:
    label = STAGE_LABELS.get(stage, stage)
    return f"{TEXT_RUN_FAILED}\uff08{label}\uff09: {message}"
