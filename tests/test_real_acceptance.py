from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_real_acceptance import AcceptanceError, run_real_acceptance


def test_run_real_acceptance_returns_summary_after_all_checks(tmp_path: Path, monkeypatch, capsys) -> None:
    from scripts import run_real_acceptance as acceptance

    output_dir = tmp_path / "current"
    priced_output_dir = tmp_path / "priced"
    unit_prices = tmp_path / "quote-unit-prices.xlsx"
    dxf_path = tmp_path / "plan.dxf"
    template_path = tmp_path / "template.xlsx"
    unit_prices.write_text("prices", encoding="utf-8")
    dxf_path.write_text("dxf", encoding="utf-8")
    template_path.write_text("template", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(
        acceptance,
        "run_quote_review_pipeline",
        lambda **kwargs: _pipeline_summary(kwargs["output_dir"], kwargs["priced_output_dir"]),
    )
    monkeypatch.setattr(acceptance, "assert_real_template_key_results", lambda checked_output_dir: calls.append(f"assert:{checked_output_dir}"))
    monkeypatch.setattr(
        acceptance,
        "check_priced_quote_outputs",
        lambda *args, **kwargs: {
            "output_dir": str(priced_output_dir),
            "files": 4,
            "automation_counts": {"自动算量": 53, "自动汇总": 46, "模板默认": 0},
            "status_counts": {"自动生成-默认推断": 38, "自动生成-异常提示": 0, "按模板生成": 0},
            "matched_unit_price_rows": 99,
        },
    )

    summary = run_real_acceptance(
        dxf_path=dxf_path,
        template_path=template_path,
        output_dir=output_dir,
        unit_prices_path=unit_prices,
        priced_output_dir=priced_output_dir,
    )

    captured = capsys.readouterr()
    assert calls == [f"assert:{output_dir}"]
    assert summary.matched_unit_price_rows == 99
    assert "Real acceptance complete" in captured.out
    assert "Matched unit price rows: 99" in captured.out


def test_run_real_acceptance_reports_failed_step(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_real_acceptance as acceptance

    monkeypatch.setattr(
        acceptance,
        "run_quote_review_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(AcceptanceError, match="real pipeline failed: boom"):
        run_real_acceptance(
            dxf_path=tmp_path / "plan.dxf",
            template_path=tmp_path / "template.xlsx",
            output_dir=tmp_path / "current",
            unit_prices_path=tmp_path / "quote-unit-prices.xlsx",
            priced_output_dir=tmp_path / "priced",
        )


def _pipeline_summary(output_dir: Path, priced_output_dir: Path):
    class Summary:
        automation_counts = {"自动算量": 53, "自动汇总": 46, "模板默认": 0}
        review_status_counts = {"自动生成-默认推断": 38, "自动生成-异常提示": 0, "按模板生成": 0}
        action_priority_counts = {"high": 3, "medium": 3, "low": 0}
        priced_output_check = {"matched_unit_price_rows": 99}
        gate_failed = False

        def __init__(self) -> None:
            self.output_dir = output_dir
            self.priced_output_dir = priced_output_dir

    return Summary()
