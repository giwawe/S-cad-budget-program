from pathlib import Path
import sys

from cad_budget.dwg_converter import convert_dwg_to_dxf


def test_convert_dwg_to_dxf_requires_converter_command(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(dwg_path, tmp_path, converter_command=None)

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERTER_NOT_CONFIGURED"


def test_convert_dwg_to_dxf_reports_failed_command(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(
        dwg_path,
        tmp_path,
        converter_command=[sys.executable, "-c", "import sys; sys.exit(7)"],
    )

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERSION_FAILED"


def test_convert_dwg_to_dxf_reports_converter_launch_failure(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(
        dwg_path,
        tmp_path,
        converter_command=["definitely-not-a-real-dwg-converter"],
    )

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERSION_FAILED"


def test_convert_dwg_to_dxf_reports_missing_output(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(
        dwg_path,
        tmp_path,
        converter_command=[sys.executable, "-c", "print('ok')"],
    )

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERSION_OUTPUT_MISSING"


def test_convert_dwg_to_dxf_returns_output_path_when_created(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(
        dwg_path,
        tmp_path,
        converter_command=[
            sys.executable,
            "-c",
            "from pathlib import Path; Path(r'{output}').write_text('dxf', encoding='utf-8')",
        ],
    )

    assert result.issue is None
    assert result.dxf_path == tmp_path / "plan.dxf"
    assert result.dxf_path.exists()
