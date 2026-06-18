from pathlib import Path

from openpyxl import load_workbook

from cad_budget.export_excel import HEADERS, export_quantity_result
from cad_budget.models import (
    DataStatus,
    HeightMode,
    Point,
    ProjectInput,
    QuantityRow,
    QuantityResult,
    RoomBoundary,
    SpaceType,
)
from cad_budget.quantity import calculate_quantities


def test_export_quantity_result_creates_workbook(tmp_path: Path):
    project_name = "Export Demo"
    project = ProjectInput(
        project_name=project_name,
        rooms=[
            RoomBoundary(
                id="room",
                name="\u4e66\u623f",
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
    sheet = workbook["\u7b97\u91cf\u8868"]
    assert sheet["A1"].value == "\u9879\u76ee\u540d\u79f0"
    assert sheet["B1"].value == project_name
    assert sheet["A3"].value == "楼层"
    assert sheet["A3"].value == HEADERS[0]
    assert sheet["B4"].value == "\u4e66\u623f"
    assert len(sheet[3]) == len(HEADERS)


def test_export_quantity_result_joins_exception_notes(tmp_path: Path):
    result = QuantityResult(
        project_name="Exception Demo",
        rows=[
            QuantityRow(
                room_id="room",
                floor="1F",
                room_name="\u4e66\u623f",
                space_type=SpaceType.NORMAL,
                height=2.8,
                height_mode=HeightMode.PROJECT_DEFAULT,
                floor_area=9.0,
                floor_perimeter=12.0,
                wall_measure_perimeter=12.0,
                open_boundary_length=0.0,
                gross_wall_area=33.6,
                window_count=0,
                window_area=0.0,
                door_opening_count=0,
                door_opening_area=0.0,
                net_wall_area=33.6,
                is_outdoor=False,
                include_in_floor_quantity=True,
                include_in_wall_paint_quantity=True,
                status=DataStatus.CONFIRMED,
                exception_notes=["\u5f02\u5e38\u7f16\u7801A", "\u7f16\u7801\u63cf\u8ff0B"],
            )
        ],
        exceptions=[],
    )
    output = tmp_path / "takeoff_with_exception.xlsx"

    export_quantity_result(result, output)

    workbook = load_workbook(output)
    sheet = workbook["\u7b97\u91cf\u8868"]
    assert sheet["S4"].value == "\u5f02\u5e38\u7f16\u7801A\uff1b\u7f16\u7801\u63cf\u8ff0B"
