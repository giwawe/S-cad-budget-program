from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

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

_COLUMN_WIDTHS = {
    "A": 10,
    "B": 16,
    "C": 14,
    "D": 10,
    "E": 12,
    "F": 12,
    "G": 16,
    "H": 16,
    "I": 14,
    "J": 10,
    "K": 12,
    "L": 12,
    "M": 12,
    "N": 14,
    "O": 14,
    "P": 16,
    "Q": 20,
    "R": 14,
    "S": 36,
}

_EDITABLE_COLUMNS = {"A", "B", "C", "D", "G", "H", "J", "K", "L", "M", "O", "P", "Q", "R", "S"}
_FORMULA_COLUMNS = {"I", "N"}
_NUMERIC_COLUMNS = {"D", "E", "F", "G", "H", "I", "K", "M", "N"}

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_EDITABLE_FILL = PatternFill("solid", fgColor="FFF2CC")
_FORMULA_FILL = PatternFill("solid", fgColor="D9EAD3")
_STATIC_FILL = PatternFill("solid", fgColor="E7E6E6")
_WHITE_FONT = Font(color="FFFFFF", bold=True)
_BOLD_FONT = Font(bold=True)


def export_quantity_result(result: QuantityResult, output_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "算量表"
    sheet["A1"] = "项目名称"
    sheet["B1"] = result.project_name
    sheet["A1"].font = _BOLD_FONT
    sheet.append([])
    sheet.append(HEADERS)

    for cell in sheet[3]:
        cell.fill = _HEADER_FILL
        cell.font = _WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_index, row in enumerate(result.rows, start=4):
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
                f"=G{row_index}*D{row_index}",
                row.window_count,
                row.window_area,
                row.door_opening_count,
                row.door_opening_area,
                f"=I{row_index}-K{row_index}",
                row.is_outdoor,
                row.include_in_floor_quantity,
                row.include_in_wall_paint_quantity,
                row.status.value,
                "；".join(row.exception_notes),
            ]
        )

    _style_data_rows(sheet)
    _configure_sheet(sheet)
    workbook.save(output_path)


def _style_data_rows(sheet) -> None:
    for row in sheet.iter_rows(min_row=4, max_row=sheet.max_row, max_col=len(HEADERS)):
        for cell in row:
            column = get_column_letter(cell.column)
            if column in _FORMULA_COLUMNS:
                cell.fill = _FORMULA_FILL
            elif column in _EDITABLE_COLUMNS:
                cell.fill = _EDITABLE_FILL
            else:
                cell.fill = _STATIC_FILL

            if column in _NUMERIC_COLUMNS:
                cell.number_format = "0.###"

            cell.alignment = Alignment(vertical="top", wrap_text=column == "S")


def _configure_sheet(sheet) -> None:
    sheet.freeze_panes = "A4"
    sheet.auto_filter.ref = f"A3:{get_column_letter(len(HEADERS))}{sheet.max_row}"
    sheet.row_dimensions[3].height = 24

    for column, width in _COLUMN_WIDTHS.items():
        sheet.column_dimensions[column].width = width
