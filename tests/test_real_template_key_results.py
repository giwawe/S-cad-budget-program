from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REAL_DXF = Path(r"D:\Desktop\10.dxf")
REAL_TEMPLATE = Path(r"D:\Desktop\清单式报价表（商品房）-修正版.xlsx")


@pytest.mark.skipif(
    not REAL_DXF.exists() or not REAL_TEMPLATE.exists(),
    reason="real local DXF/template files are not available",
)
def test_real_template_key_business_results_are_locked(tmp_path: Path) -> None:
    output_dir = tmp_path / "real-template-key-results"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    repo_root = Path(__file__).resolve().parents[1]

    pipeline = subprocess.run(
        [
            sys.executable,
            "scripts/run_real_template_quote_review.py",
            "--dxf",
            str(REAL_DXF),
            "--template",
            str(REAL_TEMPLATE),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert pipeline.returncode == 0, pipeline.stderr

    assertions = subprocess.run(
        [
            sys.executable,
            "scripts/assert_real_template_key_results.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert assertions.returncode == 0, assertions.stderr
    assert "Real template key result assertions passed" in assertions.stdout
