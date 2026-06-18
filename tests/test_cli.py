import json
from pathlib import Path

from typer.testing import CliRunner

from cad_budget.cli import app


def test_cli_calculates_json_output(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "result.json"

    result = runner.invoke(
        app,
        [
            "calculate",
            "tests/fixtures/simple_apartment.json",
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["project_name"] == "Simple Apartment"
    assert data["rows"][0]["room_name"] == "卧室"
    assert data["rows"][0]["floor_area"] == 12
