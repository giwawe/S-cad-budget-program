from pathlib import Path

from openpyxl import load_workbook

from cad_budget.export_excel import export_quantity_result
from cad_budget.models import Point, ProjectInput, RoomBoundary
from cad_budget.quantity import calculate_quantities


def test_export_quantity_result_creates_workbook(tmp_path: Path):
    project = ProjectInput(
        project_name="Export Demo",
        rooms=[
            RoomBoundary(
                id="room",
                name="书房",
                points=[
                    Point(x=0, y=0),
                    Point(x=3, y=0),
                    Point(x=3, y=3),
                    Point(x=0, y=3),
                    Point(x=0, y=0),
                ],
            )
        ],
    )
    result = calculate_quantities(project)
    output = tmp_path / "takeoff.xlsx"

    export_quantity_result(result, output)

    workbook = load_workbook(output)
    sheet = workbook["算量表"]
    assert sheet["A1"].value == "项目名称"
    assert sheet["B1"].value == "Export Demo"
    assert sheet["A3"].value == "楼层"
    assert sheet["B4"].value == "书房"
