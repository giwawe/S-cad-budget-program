from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cad_budget.cad_adapter_models import CadUnit
try:
    from scripts.assert_real_template_key_results import assert_real_template_key_results
    from scripts.check_priced_quote_outputs import check_priced_quote_outputs
    from scripts.run_real_template_quote_review import (
        DEFAULT_DXF,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_TEMPLATE,
        run_quote_review_pipeline,
    )
except ModuleNotFoundError:
    from assert_real_template_key_results import assert_real_template_key_results
    from check_priced_quote_outputs import check_priced_quote_outputs
    from run_real_template_quote_review import (
        DEFAULT_DXF,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_TEMPLATE,
        run_quote_review_pipeline,
    )


DEFAULT_UNIT_PRICES = DEFAULT_OUTPUT_DIR / "quote-unit-prices.xlsx"
DEFAULT_PRICED_OUTPUT_DIR = Path("scratch") / "cad-import-10-real-template-priced-command"


class AcceptanceError(Exception):
    pass


@dataclass(frozen=True)
class RealAcceptanceSummary:
    output_dir: Path
    priced_output_dir: Path
    automation_counts: dict[str, int]
    review_status_counts: dict[str, int]
    action_priority_counts: dict[str, int]
    matched_unit_price_rows: int


def run_real_acceptance(
    *,
    dxf_path: Path = DEFAULT_DXF,
    template_path: Path = DEFAULT_TEMPLATE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    unit_prices_path: Path = DEFAULT_UNIT_PRICES,
    priced_output_dir: Path = DEFAULT_PRICED_OUTPUT_DIR,
    unit: CadUnit = CadUnit.MILLIMETER,
    rules_path: Path | None = None,
) -> RealAcceptanceSummary:
    try:
        pipeline_summary = run_quote_review_pipeline(
            dxf_path=dxf_path,
            template_path=template_path,
            output_dir=output_dir,
            unit=unit,
            rules_path=rules_path,
            unit_prices_path=unit_prices_path,
            priced_output_dir=priced_output_dir,
            check_priced_output=True,
        )
    except Exception as exc:
        raise AcceptanceError(f"real pipeline failed: {exc}") from exc

    try:
        assert_real_template_key_results(output_dir)
    except Exception as exc:
        raise AcceptanceError(f"key result assertions failed: {exc}") from exc

    try:
        priced_check = check_priced_quote_outputs(
            priced_output_dir,
            unit_prices_path=unit_prices_path,
            expected_automation_counts=pipeline_summary.automation_counts,
            expected_status_counts=pipeline_summary.review_status_counts,
        )
    except Exception as exc:
        raise AcceptanceError(f"priced output check failed: {exc}") from exc

    summary = RealAcceptanceSummary(
        output_dir=output_dir,
        priced_output_dir=priced_output_dir,
        automation_counts=pipeline_summary.automation_counts,
        review_status_counts=pipeline_summary.review_status_counts,
        action_priority_counts=pipeline_summary.action_priority_counts,
        matched_unit_price_rows=int(priced_check["matched_unit_price_rows"]),
    )
    _print_summary(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full real-template acceptance check.")
    parser.add_argument("--dxf", type=Path, default=DEFAULT_DXF, help="DXF file to import.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Residential quote template workbook.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for current regression outputs.")
    parser.add_argument("--unit-prices", type=Path, default=DEFAULT_UNIT_PRICES, help="Global unit price workbook.")
    parser.add_argument("--priced-output-dir", type=Path, default=DEFAULT_PRICED_OUTPUT_DIR, help="Directory for quote-priced outputs.")
    parser.add_argument("--unit", choices=[unit.value for unit in CadUnit], default=CadUnit.MILLIMETER.value)
    parser.add_argument("--rules", type=Path, default=None, help="Optional residential quote rules JSON.")
    args = parser.parse_args()

    try:
        run_real_acceptance(
            dxf_path=args.dxf,
            template_path=args.template,
            output_dir=args.output_dir,
            unit_prices_path=args.unit_prices,
            priced_output_dir=args.priced_output_dir,
            unit=CadUnit(args.unit),
            rules_path=args.rules,
        )
    except AcceptanceError as exc:
        raise SystemExit(str(exc))


def _print_summary(summary: RealAcceptanceSummary) -> None:
    print("Real acceptance complete")
    print(f"Output directory: {summary.output_dir}")
    print(f"Priced output directory: {summary.priced_output_dir}")
    print("Automation counts: " + _format_counts(summary.automation_counts))
    print("Review status counts: " + _format_counts(summary.review_status_counts))
    print("Action priority counts: " + _format_counts(summary.action_priority_counts))
    print(f"Matched unit price rows: {summary.matched_unit_price_rows}")


def _format_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{label}={count}" for label, count in counts.items())


if __name__ == "__main__":
    main()
