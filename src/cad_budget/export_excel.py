from pathlib import Path

from openpyxl import Workbook

from cad_budget.models import QuantityResult


HEADERS = [
    "楼层",
    "空间名称",
    "空间类型",
    "层高",
    "地面面积",
    "地面周长",
    "墙面计量周长",
    "开放边界长度",
    "墙面毛面积",
    "窗数量",
    "窗面积",
    "门洞数量",
    "门洞面积",
    "墙面净面积",
    "是否室外空间",
    "是否计入室内地面",
    "是否计入室内墙面乳胶漆",
    "识别状态",
    "异常说明",
]


def export_quantity_result(result: QuantityResult, output_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "算量表"
    sheet["A1"] = "项目名称"
    sheet["B1"] = result.project_name
    sheet.append([])
    sheet.append(HEADERS)

    for row in result.rows:
        sheet.append(
            [
                row.floor,
                row.room_name,
                row.space_type.value,
                row.height,
                row.floor_area,
                row.floor_perimeter,
                row.wall_measure_perimeter,
                row.open_boundary_length,
                row.gross_wall_area,
                row.window_count,
                row.window_area,
                row.door_opening_count,
                row.door_opening_area,
                row.net_wall_area,
                row.is_outdoor,
                row.include_in_floor_quantity,
                row.include_in_wall_paint_quantity,
                row.status.value,
                "；".join(row.exception_notes),
            ]
        )

    workbook.save(output_path)
