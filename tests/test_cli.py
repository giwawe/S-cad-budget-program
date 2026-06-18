import json
from pathlib import Path

from openpyxl import load_workbook
from typer.testing import CliRunner

from cad_budget.cli import app


def test_cli_calculates_json_output(tmp_path: Path):
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "simple_apartment.json"
    output = tmp_path / "result.json"

    result = runner.invoke(
        app,
        [
            "calculate",
            str(fixture),
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["project_name"] == "Simple Apartment"
    assert data["rows"][0]["room_name"] == "卧室"
    assert data["rows"][0]["floor_area"] == 12


def test_cli_creates_nested_output_directory(tmp_path: Path):
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "simple_apartment.json"
    output = tmp_path / "nested" / "dir" / "result.json"

    result = runner.invoke(
        app,
        [
            "calculate",
            str(fixture),
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert output.parent.is_dir()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["rows"][0]["room_name"] == "卧室"


def test_cli_writes_nested_excel_output(tmp_path: Path):
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "simple_apartment.json"
    json_output = tmp_path / "nested" / "json" / "result.json"
    excel_output = tmp_path / "nested" / "excel" / "result.xlsx"

    result = runner.invoke(
        app,
        [
            "calculate",
            str(fixture),
            "--json-output",
            str(json_output),
            "--excel-output",
            str(excel_output),
        ],
    )

    assert result.exit_code == 0
    assert json_output.exists()
    assert excel_output.exists()
    workbook = load_workbook(excel_output)
    assert workbook.sheetnames == ["算量表"]
    assert "Wrote" in result.output


def test_cli_reports_excel_output_failure_when_parent_is_file(tmp_path: Path):
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "simple_apartment.json"
    output = tmp_path / "result.json"
    blocked_dir = tmp_path / "not_a_dir"
    blocked_dir.write_text("blocked", encoding="utf-8")
    excel_output = blocked_dir / "result.xlsx"

    result = runner.invoke(
        app,
        [
            "calculate",
            str(fixture),
            "--json-output",
            str(output),
            "--excel-output",
            str(excel_output),
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to write Excel output" in error_text
    assert "Traceback" not in error_text
    assert "Wrote" not in error_text


def test_cli_reports_missing_input_file(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "output" / "result.json"

    result = runner.invoke(
        app,
        [
            "calculate",
            str(tmp_path / "missing.json"),
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to read input JSON" in error_text
    assert "missing.json" in error_text
    assert "Traceback" not in error_text


def test_cli_reports_invalid_json_input(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "output" / "result.json"
    bad_input = tmp_path / "bad.json"
    bad_input.write_text("{invalid}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "calculate",
            str(bad_input),
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Invalid project JSON" in error_text
    assert "Traceback" not in error_text


def test_cli_reports_non_utf8_input(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "output" / "result.json"
    bad_input = tmp_path / "non_utf8.bin"
    bad_input.write_bytes(bytes([0xFF, 0xFE, 0xFD]))

    result = runner.invoke(
        app,
        [
            "calculate",
            str(bad_input),
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to read input JSON" in error_text
    assert "non_utf8.bin" in error_text
    assert "Traceback" not in error_text
