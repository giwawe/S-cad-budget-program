import json
from pathlib import Path

import ezdxf
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


def test_cli_reports_invalid_room_geometry_without_traceback(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "result.json"
    bad_input = tmp_path / "bad_room.json"
    bad_input.write_text(
        json.dumps(
            {
                "project_name": "Bad Geometry",
                "default_height": 2.8,
                "rooms": [
                    {
                        "id": "bow-tie",
                        "points": [
                            {"x": 0, "y": 0},
                            {"x": 2, "y": 2},
                            {"x": 0, "y": 2},
                            {"x": 2, "y": 0},
                            {"x": 0, "y": 0},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

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
    assert "Failed to calculate quantities" in error_text
    assert "Traceback" not in error_text


def test_cli_import_cad_dxf_writes_project_json(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    dxf_path = tmp_path / "plan.dxf"
    doc.saveas(dxf_path)
    output = tmp_path / "project.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "import-cad",
            str(dxf_path),
            "--json-output",
            str(output),
            "--unit",
            "mm",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["project_name"] == "plan"
    assert len(data["rooms"]) == 1


def test_cli_import_cad_dwg_requires_converter(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")
    output = tmp_path / "project.json"
    runner = CliRunner()

    result = runner.invoke(app, ["import-cad", str(dwg_path), "--json-output", str(output)])

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "DWG input requires a configured DWG-to-DXF converter" in error_text
    assert not output.exists()


def test_cli_import_cad_dwg_reports_conversion_output_path_error(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")
    blocked_parent = tmp_path / "not_a_dir"
    blocked_parent.write_text("blocked", encoding="utf-8")
    output = blocked_parent / "project.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "import-cad",
            str(dwg_path),
            "--json-output",
            str(output),
            "--dwg-converter",
            "dummy-converter",
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to prepare DWG conversion output" in error_text
    assert "Traceback" not in error_text
    assert not output.exists()


def test_cli_import_cad_unsupported_extension_exits_1(tmp_path: Path):
    cad_path = tmp_path / "plan.txt"
    cad_path.write_text("fake", encoding="utf-8")
    output = tmp_path / "project.json"
    runner = CliRunner()

    result = runner.invoke(app, ["import-cad", str(cad_path), "--json-output", str(output)])

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Unsupported CAD file extension" in error_text
    assert ".txt" in error_text
    assert not output.exists()


def test_cli_import_cad_dxf_blocker_exits_1_without_writing(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    dxf_path = tmp_path / "empty.dxf"
    doc.saveas(dxf_path)
    output = tmp_path / "project.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "import-cad",
            str(dxf_path),
            "--json-output",
            str(output),
            "--unit",
            "mm",
        ],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "blocker: QUOTE_ROOM_MISSING" in error_text
    assert not output.exists()


def test_cli_calculate_writes_exterior_rows_to_json(tmp_path: Path):
    input_json = tmp_path / "exterior_project.json"
    output = tmp_path / "result.json"
    input_json.write_text(
        json.dumps(
            {
                "project_name": "Exterior CLI",
                "default_height": 2.8,
                "floor_heights": {"1F": 3.0},
                "exterior_walls": [
                    {
                        "id": "ext-wall",
                        "layer": "QUOTE_EXT_WALL",
                        "floor": "1F",
                        "points": [{"x": 0, "y": 0}, {"x": 4, "y": 0}],
                    }
                ],
                "exterior_openings": [
                    {
                        "id": "ext-open",
                        "layer": "QUOTE_EXT_OPENING",
                        "floor": "1F",
                        "points": [{"x": 1, "y": 0}, {"x": 2, "y": 0}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["calculate", str(input_json), "--json-output", str(output)])

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["rows"] == []
    assert data["exterior_rows"][0]["gross_area"] == 12.0
    assert data["exterior_rows"][0]["net_area"] == 9.0


def test_cli_import_excel_writes_edited_quantity_json(tmp_path: Path):
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "simple_apartment.json"
    calculated_json = tmp_path / "result.json"
    excel_output = tmp_path / "result.xlsx"

    calculate_result = runner.invoke(
        app,
        [
            "calculate",
            str(fixture),
            "--json-output",
            str(calculated_json),
            "--excel-output",
            str(excel_output),
        ],
    )
    assert calculate_result.exit_code == 0

    workbook = load_workbook(excel_output)
    sheet = workbook.active
    sheet["D4"] = 3.0
    sheet["G4"] = 10.0
    sheet["K4"] = 2.0
    workbook.save(excel_output)

    imported_json = tmp_path / "edited-result.json"
    import_result = runner.invoke(
        app,
        [
            "import-excel",
            str(excel_output),
            "--json-output",
            str(imported_json),
        ],
    )

    assert import_result.exit_code == 0
    data = json.loads(imported_json.read_text(encoding="utf-8"))
    assert data["rows"][0]["gross_wall_area"] == 30.0
    assert data["rows"][0]["net_wall_area"] == 28.0


def test_cli_quote_writes_residential_fitout_excel(tmp_path: Path):
    runner = CliRunner()
    input_json = tmp_path / "result.json"
    template = tmp_path / "template.xlsx"
    output = tmp_path / "quote.xlsx"
    input_json.write_text(json.dumps(_quantity_result_payload()), encoding="utf-8")
    _write_quote_cli_template(template, include_fitout=True)

    result = runner.invoke(app, ["quote", str(input_json), "--template", str(template), "--excel-output", str(output)])

    assert result.exit_code == 0
    assert output.exists()
    workbook = load_workbook(output, data_only=False)
    sheet = workbook.active
    assert workbook.sheetnames == ["商品房整装报价"]
    assert sheet["B5"].value == "客厅工程"
    assert sheet["J3"].value == "数量来源"
    assert sheet["O3"].value == "复核备注"
    assert "Wrote" in result.output


def test_cli_quote_reports_missing_template_without_traceback(tmp_path: Path):
    runner = CliRunner()
    input_json = tmp_path / "result.json"
    input_json.write_text(json.dumps(_quantity_result_payload()), encoding="utf-8")
    output = tmp_path / "quote.xlsx"

    result = runner.invoke(
        app,
        ["quote", str(input_json), "--template", str(tmp_path / "missing.xlsx"), "--excel-output", str(output)],
    )

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to generate quote Excel" in error_text
    assert "Traceback" not in error_text
    assert not output.exists()


def test_cli_quote_reports_missing_fitout_sheet_without_traceback(tmp_path: Path):
    runner = CliRunner()
    input_json = tmp_path / "result.json"
    template = tmp_path / "template.xlsx"
    output = tmp_path / "quote.xlsx"
    input_json.write_text(json.dumps(_quantity_result_payload()), encoding="utf-8")
    _write_quote_cli_template(template, include_fitout=False)

    result = runner.invoke(app, ["quote", str(input_json), "--template", str(template), "--excel-output", str(output)])

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Failed to generate quote Excel" in error_text
    assert "整装" in error_text
    assert "Traceback" not in error_text


def test_cli_quote_reports_invalid_quantity_json_without_traceback(tmp_path: Path):
    runner = CliRunner()
    input_json = tmp_path / "bad.json"
    template = tmp_path / "template.xlsx"
    output = tmp_path / "quote.xlsx"
    input_json.write_text(json.dumps({"project_name": "Not A Result"}), encoding="utf-8")
    _write_quote_cli_template(template, include_fitout=True)

    result = runner.invoke(app, ["quote", str(input_json), "--template", str(template), "--excel-output", str(output)])

    assert result.exit_code == 1
    error_text = (result.stdout or "") + (result.stderr or "")
    assert "Invalid quantity result JSON" in error_text
    assert "Traceback" not in error_text


def _quantity_result_payload():
    return {
        "project_name": "Quote CLI",
        "rows": [
            {
                "room_id": "living",
                "floor": None,
                "room_name": "客厅",
                "space_type": "normal",
                "height": 2.8,
                "height_mode": "project_default",
                "floor_area": 20.0,
                "floor_perimeter": 0,
                "wall_measure_perimeter": 0,
                "open_boundary_length": 0,
                "gross_wall_area": 50.0,
                "window_count": 0,
                "window_area": 0,
                "door_opening_count": 0,
                "door_opening_area": 0,
                "net_wall_area": 50.0,
                "is_outdoor": False,
                "include_in_floor_quantity": True,
                "include_in_wall_paint_quantity": True,
                "status": "confirmed",
                "exception_notes": [],
            }
        ],
        "exterior_rows": [],
        "exceptions": [],
    }


def _write_quote_cli_template(path: Path, *, include_fitout: bool) -> None:
    workbook = load_workbook(path) if path.exists() else None
    if workbook is None:
        from openpyxl import Workbook

        workbook = Workbook()
    half = workbook.active
    half.title = "半包"
    half.append(["工程(预) 算表"])
    if include_fitout:
        sheet = workbook.create_sheet("整装")
        sheet.append(["工程(预) 算表"])
        sheet.append(["名称：Demo"])
        sheet.append(["编号", "项目名称", "单位", "数量", "材料费(元)", None, "人工费\n(元)", "总价(元)", "材料及工艺说明"])
        sheet.append([None, None, None, None, "主材\n单价", "辅材\n单价"])
        sheet.append(["一", "客厅工程"])
        sheet.append([1, "顶面批嵌", "M2", 1, 0, 15, 10, None, "说明"])
        sheet.append([2, "墙面乳胶漆", "M2", 1, 10, 0, 10, None, "说明"])
        sheet.append([3, "地面砖铺贴(750X1500)", "M2", 1, 0, 36, 60, None, "说明"])
    workbook.save(path)
