from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from cad_budget.models import DataStatus, QuantityResult, QuantityRow


FITOUT_SHEET_NAME = "\u6574\u88c5"
QUOTE_SHEET_NAME = "\u5546\u54c1\u623f\u6574\u88c5\u62a5\u4ef7"
QUOTE_HEADERS = [
    "\u7f16\u53f7",
    "\u9879\u76ee\u540d\u79f0",
    "\u5355\u4f4d",
    "\u6570\u91cf",
    "\u6750\u6599\u8d39(\u5143)",
    None,
    "\u4eba\u5de5\u8d39\n(\u5143)",
    "\u603b\u4ef7(\u5143)",
    "\u6750  \u6599  \u53ca  \u5de5  \u827a  \u8bf4  \u660e",
    "\u6570\u91cf\u6765\u6e90",
    "\u6765\u6e90\u7a7a\u95f4",
    "\u7a7a\u95f4ID",
    "\u8ba1\u91cf\u53e3\u5f84",
    "\u590d\u6838\u72b6\u6001",
    "\u590d\u6838\u5907\u6ce8",
]
QUOTE_SUBHEADERS = [None, None, None, None, "\u4e3b\u6750\n\u5355\u4ef7", "\u8f85\u6750\n\u5355\u4ef7"]

_SPACE_TEMPLATE_KEYWORDS = {
    "\u5ba2\u5385",
    "\u9910\u5385",
    "\u4e3b\u5367",
    "\u6b21\u5367",
    "\u5ba2\u5367",
    "\u5367\u5ba4",
    "\u7384\u5173",
    "\u8fc7\u9053",
    "\u53a8\u623f",
    "\u536b\u751f\u95f4",
    "\u4e3b\u536b",
    "\u516c\u536b",
    "\u9732\u53f0",
    "\u9633\u53f0",
}
_NON_SPACE_SECTION_KEYWORDS = {
    "\u5176\u4ed6",
    "\u6c34\u7535",
    "\u4e3b\u6750",
    "\u5168\u5c4b\u5b9a\u5236",
    "\u5ba4\u5185\u95e8",
    "\u536b\u6d74",
    "\u5f00\u5173",
    "\u706f\u9970",
    "\u7a97\u5e18",
    "\u7f8e\u7f1d",
}
_GENERAL_ROOM_ITEMS = [
    "\u8f7b\u94a2\u9f99\u9aa8\u5e73\u9876",
    "\u9876\u9762\u6279\u5d4c",
    "\u9876\u9762\u4e73\u80f6\u6f06",
    "\u5899\u9762\u754c\u9762\u5242\u5904\u7406",
    "\u5899\u9762\u6279\u5d4c",
    "\u5899\u9762\u4e73\u80f6\u6f06",
    "\u5730\u9762\u7816\u94fa\u8d34(750X1500)",
]
_WET_ROOM_BASE_ITEMS = [
    "\u5730\u9762\u627e\u5e73",
    "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406",
    "\u5730\u9762\u7816\u94fa\u8d34(750X1500)",
]
_WALL_TILE_VARIANTS = ["\u5899\u9762\u8d34\u74f7\u7816(600x1200)", "\u5899\u9762\u8d34\u74f7\u7816(600X1200)"]
_TERRACE_ITEMS = [
    "\u5730\u9762\u627e\u5e73",
    "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406",
    "\u9876\u9762\u6279\u5d4c",
    "\u9876\u9762\u4e73\u80f6\u6f06",
    "\u5899\u9762\u6279\u5d4c",
    "\u5899\u9762\u754c\u9762\u5242\u5904\u7406",
    "\u5899\u9762\u4e73\u80f6\u6f06",
    "\u5899\u9762\u8d34\u74f7\u7816(600x1200)",
    "\u5730\u9762\u7816\u94fa\u8d34(750X1500)",
]
_SECTION_NUMERALS = [
    "\u4e00",
    "\u4e8c",
    "\u4e09",
    "\u56db",
    "\u4e94",
    "\u516d",
    "\u4e03",
    "\u516b",
    "\u4e5d",
    "\u5341",
    "\u5341\u4e00",
    "\u5341\u4e8c",
    "\u5341\u4e09",
    "\u5341\u56db",
    "\u5341\u4e94",
    "\u5341\u516d",
    "\u5341\u4e03",
    "\u5341\u516b",
    "\u5341\u4e5d",
    "\u4e8c\u5341",
]

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_SECTION_FILL = PatternFill("solid", fgColor="D9EAD3")
_REVIEW_FILL = PatternFill("solid", fgColor="EADCF8")
_WHITE_FONT = Font(color="FFFFFF", bold=True)
_BOLD_FONT = Font(bold=True)

_KITCHEN_WATERPROOF_WALL_HEIGHT = 0.3
_BATHROOM_WATERPROOF_WALL_HEIGHT = 1.8
_WALL_TILE_HEIGHT = 2.5


@dataclass
class QuoteTemplateItem:
    number: int
    name: str
    unit: str | None
    template_quantity: float | int | None
    main_material_price: float | int
    auxiliary_material_price: float | int
    labor_price: float | int
    description: str | None


@dataclass
class QuoteTemplateSection:
    name: str
    items: list[QuoteTemplateItem] = field(default_factory=list)


@dataclass
class QuoteTemplate:
    sheet_name: str
    sections: list[QuoteTemplateSection]


@dataclass
class QuoteAggregateQuantity:
    quantity: float
    basis: str
    rooms: list[QuantityRow]


def parse_quote_template(template_path: Path) -> QuoteTemplate:
    workbook = load_workbook(template_path, data_only=False)
    if FITOUT_SHEET_NAME not in workbook.sheetnames:
        raise ValueError("Quote template must contain an '\u6574\u88c5' worksheet.")
    sheet = workbook[FITOUT_SHEET_NAME]

    sections: list[QuoteTemplateSection] = []
    current_section: QuoteTemplateSection | None = None
    for row_index in range(5, sheet.max_row + 1):
        number = sheet.cell(row=row_index, column=1).value
        name = _as_text(sheet.cell(row=row_index, column=2).value)
        if not name:
            continue
        if _is_section_row(number, sheet, row_index):
            current_section = QuoteTemplateSection(name=name)
            sections.append(current_section)
            continue
        if current_section is None or not isinstance(number, int) or _is_skip_row(name):
            continue
        current_section.items.append(
            QuoteTemplateItem(
                number=number,
                name=name,
                unit=_as_text(sheet.cell(row=row_index, column=3).value),
                template_quantity=sheet.cell(row=row_index, column=4).value,
                main_material_price=_number_or_zero(sheet.cell(row=row_index, column=5).value),
                auxiliary_material_price=_number_or_zero(sheet.cell(row=row_index, column=6).value),
                labor_price=_number_or_zero(sheet.cell(row=row_index, column=7).value),
                description=_as_text(sheet.cell(row=row_index, column=9).value),
            )
        )

    return QuoteTemplate(sheet_name=FITOUT_SHEET_NAME, sections=[section for section in sections if section.items])


def export_residential_quote(result: QuantityResult, template_path: Path, output_path: Path) -> None:
    template = parse_quote_template(template_path)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = QUOTE_SHEET_NAME
    _write_quote_title(sheet, result.project_name)

    subtotal_rows: list[int] = []
    section_index = 0
    item_index = _build_item_index(template)
    included_rooms = [room for room in result.rows if _should_generate_room_section(room)]

    for room in included_rooms:
        section_index += 1
        item_names = _item_names_for_room(room, item_index)
        items = [item_index[name] for name in item_names if name in item_index]
        if not items:
            continue
        subtotal_rows.append(_append_section(sheet, _section_label(section_index), f"{room.room_name}\u5de5\u7a0b", items, room))

    for section in template.sections:
        if _is_space_template_section(section.name):
            continue
        section_index += 1
        subtotal_rows.append(_append_section(sheet, _section_label(section_index), section.name, section.items, None, included_rooms))

    _append_summary_rows(sheet, subtotal_rows)
    _write_automation_summary(sheet)
    _configure_sheet(sheet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def _write_quote_title(sheet, project_name: str) -> None:
    sheet.append(["\u5de5\u7a0b(\u9884) \u7b97\u8868"])
    sheet.append([f"\u540d\u79f0\uff1a{project_name}"])
    sheet.append(QUOTE_HEADERS)
    sheet.append(QUOTE_SUBHEADERS)
    for row in sheet.iter_rows(min_row=1, max_row=4):
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for cell in sheet[3]:
        cell.fill = _HEADER_FILL
        cell.font = _WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for cell in sheet[4]:
        cell.fill = _HEADER_FILL
        cell.font = _WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet["A1"].font = Font(bold=True, size=14)


def _append_section(
    sheet,
    section_number: str,
    section_name: str,
    items: list[QuoteTemplateItem],
    room: QuantityRow | None,
    included_rooms: list[QuantityRow] | None = None,
) -> int:
    sheet.append([section_number, section_name])
    section_row = sheet.max_row
    for cell in sheet[section_row]:
        cell.fill = _SECTION_FILL
        cell.font = _BOLD_FONT

    first_item_row = sheet.max_row + 1
    for item_number, item in enumerate(items, start=1):
        row_index = sheet.max_row + 1
        aggregate = _aggregate_quantity_for_item(item.name, included_rooms or []) if room is None else None
        if room is not None:
            quantity = _quantity_for_item(item.name, room)
        elif aggregate is not None:
            quantity = aggregate.quantity
        else:
            quantity = item.template_quantity
        review_values = _review_values_for_item(item.name, room, aggregate)
        sheet.append(
            [
                item_number,
                item.name,
                item.unit,
                quantity,
                item.main_material_price,
                item.auxiliary_material_price,
                item.labor_price,
                f"=D{row_index}*(E{row_index}+F{row_index}+G{row_index})",
                item.description,
                *review_values,
            ]
        )
        _style_item_row(sheet, row_index)

    subtotal_row = sheet.max_row + 1
    sheet.append([None, "\u5c0f \u8ba1", None, None, None, None, None, f"=SUM(H{first_item_row}:H{subtotal_row - 1})"])
    sheet.cell(row=subtotal_row, column=2).font = _BOLD_FONT
    sheet.cell(row=subtotal_row, column=8).font = _BOLD_FONT
    return subtotal_row


def _append_summary_rows(sheet, subtotal_rows: list[int]) -> None:
    direct_row = sheet.max_row + 1
    direct_formula = "=" + "+".join(f"H{row}" for row in subtotal_rows) if subtotal_rows else "=0"
    sheet.append(["A", "\u76f4\u63a5\u8d39\u5408\u8ba1(\u4e00+\u2026...\u5341)", None, None, None, None, None, direct_formula])
    manage_row = sheet.max_row + 1
    sheet.append(["B", "\u5de5\u7a0b\u7ba1\u7406\u8d39(D=A* 5%)", None, None, None, None, None, f"=H{direct_row}*0.05"])
    tax_row = sheet.max_row + 1
    sheet.append(["C", "\u7a0e\u91d1E=(A+B)* 3%", None, None, None, None, None, 0])
    total_row = sheet.max_row + 1
    sheet.append(["D", "\u5de5\u7a0b\u603b\u9020\u4ef7F=(A+B+C)", None, None, None, None, None, f"=SUM(H{direct_row}:H{tax_row})"])
    for row_index in range(direct_row, total_row + 1):
        sheet.cell(row=row_index, column=1).font = _BOLD_FONT
        sheet.cell(row=row_index, column=2).font = _BOLD_FONT
        sheet.cell(row=row_index, column=8).font = _BOLD_FONT


def _style_item_row(sheet, row_index: int) -> None:
    for column_index in range(1, 16):
        cell = sheet.cell(row=row_index, column=column_index)
        cell.alignment = Alignment(vertical="top", wrap_text=column_index in {9, 13, 15})
        if column_index in {4, 5, 6, 7, 8}:
            cell.number_format = "0.###"
        if column_index >= 10:
            cell.fill = _REVIEW_FILL


def _configure_sheet(sheet) -> None:
    widths = {
        "A": 8,
        "B": 24,
        "C": 8,
        "D": 10,
        "E": 12,
        "F": 12,
        "G": 12,
        "H": 14,
        "I": 48,
        "J": 12,
        "K": 12,
        "L": 12,
        "M": 18,
        "N": 14,
        "O": 18,
        "Q": 16,
        "R": 10,
        "S": 12,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A3:O{sheet.max_row}"


def _write_automation_summary(sheet) -> None:
    labels = [
        "\u81ea\u52a8\u7b97\u91cf",
        "\u81ea\u52a8\u6c47\u603b",
        "\u6a21\u677f\u9ed8\u8ba4",
    ]
    counts = {label: 0 for label in labels}
    for row_index in range(5, sheet.max_row + 1):
        source = sheet.cell(row=row_index, column=10).value
        if source in counts:
            counts[source] += 1

    sheet["Q1"] = "\u62a5\u4ef7\u81ea\u52a8\u5316\u7edf\u8ba1"
    sheet["Q1"].font = _BOLD_FONT
    sheet["Q1"].fill = _SECTION_FILL
    for column_index, header in enumerate(["\u6570\u91cf\u6765\u6e90", "\u884c\u6570", "\u5360\u6bd4"], start=17):
        cell = sheet.cell(row=2, column=column_index, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for offset, label in enumerate(labels, start=3):
        sheet.cell(row=offset, column=17, value=label)
        sheet.cell(row=offset, column=18, value=counts[label])
        percent_cell = sheet.cell(row=offset, column=19, value=f"=R{offset}/SUM(R3:R5)")
        percent_cell.number_format = "0.0%"
        for column_index in range(17, 20):
            sheet.cell(row=offset, column=column_index).fill = _REVIEW_FILL


def _build_item_index(template: QuoteTemplate) -> dict[str, QuoteTemplateItem]:
    item_index: dict[str, QuoteTemplateItem] = {}
    for section in template.sections:
        for item in section.items:
            item_index.setdefault(item.name, item)
    return item_index


def _item_names_for_room(room: QuantityRow, item_index: dict[str, QuoteTemplateItem]) -> list[str]:
    name = room.room_name
    if any(keyword in name for keyword in ["\u53a8\u623f", "\u536b", "\u6d17\u624b\u95f4", "\u536b\u751f\u95f4"]):
        names = _WET_ROOM_BASE_ITEMS.copy()
        wall_tile = next((variant for variant in _WALL_TILE_VARIANTS if variant in item_index), None)
        if wall_tile is not None:
            names.insert(2, wall_tile)
        return names
    if any(keyword in name for keyword in ["\u9732\u53f0", "\u9633\u53f0"]):
        return _TERRACE_ITEMS
    return _GENERAL_ROOM_ITEMS


def _quantity_for_item(item_name: str, room: QuantityRow) -> float:
    if item_name in {
        "\u8f7b\u94a2\u9f99\u9aa8\u5e73\u9876",
        "\u9876\u9762\u6279\u5d4c",
        "\u9876\u9762\u4e73\u80f6\u6f06",
        "\u5730\u9762\u7816\u94fa\u8d34(750X1500)",
        "\u5730\u9762\u627e\u5e73",
    }:
        return _round_quantity(room.floor_area)
    if item_name == "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406":
        if "\u53a8\u623f" in room.room_name:
            return _round_quantity(room.floor_area + room.wall_measure_perimeter * _KITCHEN_WATERPROOF_WALL_HEIGHT)
        return _round_quantity(room.floor_area + room.wall_measure_perimeter * _BATHROOM_WATERPROOF_WALL_HEIGHT)
    if item_name in {
        "\u5899\u9762\u754c\u9762\u5242\u5904\u7406",
        "\u5899\u9762\u6279\u5d4c",
        "\u5899\u9762\u4e73\u80f6\u6f06",
    }:
        return _round_quantity(room.net_wall_area)
    if item_name in {
        "\u5899\u9762\u8d34\u74f7\u7816(600x1200)",
        "\u5899\u9762\u8d34\u74f7\u7816(600X1200)",
    }:
        return _wet_wall_tile_area(room)
    return 0


def _aggregate_quantity_for_item(item_name: str, rooms: list[QuantityRow]) -> QuoteAggregateQuantity | None:
    if not rooms:
        return None
    if item_name in {
        "\u5783\u573e\u6e05\u8fd0\u8d39",
        "\u6750\u6599\u642c\u8fd0\u8d39",
        "\u5730\u9762\u7816\u73b0\u573a\u7ef4\u62a4\u8d39",
        "\u5f3a\u7535\u5e03\u7ebf",
        "\u5f31\u7535\u5e03\u7ebf",
        "\u6c34\u8def\u5e03\u7ba1",
        "\u6c34\u6ce5\u5899\u5f00\u69fd",
        "\u8865\u7ebf\u3001\u7ba1\u69fd\u53ca\u96f6\u661f\u4fee\u8865",
    }:
        floor_rooms = [room for room in rooms if room.include_in_floor_quantity]
        return QuoteAggregateQuantity(
            quantity=_round_quantity(sum(room.floor_area for room in floor_rooms)),
            basis="\u5ba4\u5185\u5730\u9762\u9762\u79ef\u6c47\u603b",
            rooms=floor_rooms,
        )
    if item_name == "\u7f8e\u7f1d":
        floor_rooms = [room for room in rooms if room.include_in_floor_quantity]
        wall_tile_rooms = [room for room in rooms if _room_has_wall_tile(room)]
        return QuoteAggregateQuantity(
            quantity=_round_quantity(
                sum(room.floor_area for room in floor_rooms) + sum(_wet_wall_tile_area(room) for room in wall_tile_rooms)
            ),
            basis="\u5730\u7816\u9762\u79ef+2.5m\u4ee5\u4e0b\u5899\u9762\u8d34\u7816\u9762\u79ef",
            rooms=list({room.room_id: room for room in [*floor_rooms, *wall_tile_rooms]}.values()),
        )
    return None


def _review_values_for_item(
    item_name: str,
    room: QuantityRow | None,
    aggregate: QuoteAggregateQuantity | None = None,
) -> list[str | None]:
    if aggregate is not None:
        return [
            "\u81ea\u52a8\u6c47\u603b",
            "\u5168\u5c4b",
            None,
            aggregate.basis,
            _review_status_for_rooms(aggregate.rooms),
            _review_note_for_rooms(aggregate.rooms),
        ]
    if room is None:
        return [
            "\u6a21\u677f\u9ed8\u8ba4",
            None,
            None,
            "\u6a21\u677f\u9ed8\u8ba4\u6570\u91cf",
            "\u6309\u6a21\u677f\u751f\u6210",
            None,
        ]
    return [
        "\u81ea\u52a8\u7b97\u91cf",
        room.room_name,
        room.room_id,
        _measure_basis_for_item(item_name, room),
        _review_status_for_room(room),
        _review_note_for_room(room),
    ]


def _review_status_for_rooms(rooms: list[QuantityRow]) -> str:
    if any(room.status == DataStatus.NEEDS_REVIEW for room in rooms):
        return "\u81ea\u52a8\u751f\u6210-\u5f02\u5e38\u63d0\u793a"
    if any(room.status == DataStatus.DEFAULT_INFERRED for room in rooms):
        return "\u81ea\u52a8\u751f\u6210-\u9ed8\u8ba4\u63a8\u65ad"
    return "\u81ea\u52a8\u751f\u6210"


def _review_note_for_rooms(rooms: list[QuantityRow]) -> str | None:
    notes: list[str] = []
    for room in rooms:
        if room.status in {DataStatus.DEFAULT_INFERRED, DataStatus.NEEDS_REVIEW}:
            notes.extend(room.exception_notes)
    return "\uff1b".join(notes) if notes else None


def _review_status_for_room(room: QuantityRow) -> str:
    if room.status == DataStatus.DEFAULT_INFERRED:
        return "\u81ea\u52a8\u751f\u6210-\u9ed8\u8ba4\u63a8\u65ad"
    if room.status == DataStatus.NEEDS_REVIEW:
        return "\u81ea\u52a8\u751f\u6210-\u5f02\u5e38\u63d0\u793a"
    return "\u81ea\u52a8\u751f\u6210"


def _review_note_for_room(room: QuantityRow) -> str | None:
    if room.status not in {DataStatus.DEFAULT_INFERRED, DataStatus.NEEDS_REVIEW}:
        return None
    notes = list(room.exception_notes)
    if not notes:
        return f"\u7b97\u91cf\u72b6\u6001\uff1a{room.status.value}"
    return "\uff1b".join(notes)


def _measure_basis_for_item(item_name: str, room: QuantityRow) -> str:
    if item_name == "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406":
        if "\u53a8\u623f" in room.room_name:
            return "\u5730\u9762\u9762\u79ef+0.3m\u4ee5\u4e0b\u5899\u9762\u9762\u79ef"
        return "\u5730\u9762\u9762\u79ef+1.8m\u4ee5\u4e0b\u5899\u9762\u9762\u79ef"
    if item_name in {
        "\u8f7b\u94a2\u9f99\u9aa8\u5e73\u9876",
        "\u9876\u9762\u6279\u5d4c",
        "\u9876\u9762\u4e73\u80f6\u6f06",
        "\u5730\u9762\u7816\u94fa\u8d34(750X1500)",
        "\u5730\u9762\u627e\u5e73",
    }:
        return "\u5730\u9762\u9762\u79ef"
    if item_name in {
        "\u5899\u9762\u754c\u9762\u5242\u5904\u7406",
        "\u5899\u9762\u6279\u5d4c",
        "\u5899\u9762\u4e73\u80f6\u6f06",
    }:
        return "\u5899\u9762\u51c0\u9762\u79ef"
    if item_name in {
        "\u5899\u9762\u8d34\u74f7\u7816(600x1200)",
        "\u5899\u9762\u8d34\u74f7\u7816(600X1200)",
    }:
        return "2.5m\u4ee5\u4e0b\u5899\u9762\u8d34\u7816\u9762\u79ef"
    return "\u81ea\u52a8\u7b97\u91cf"


def _wet_wall_tile_area(room: QuantityRow) -> float:
    return _round_quantity(max(0, room.wall_measure_perimeter * _WALL_TILE_HEIGHT - room.window_area))


def _should_generate_room_section(room: QuantityRow) -> bool:
    if room.status == DataStatus.EXCLUDED:
        return False
    return room.include_in_floor_quantity or room.include_in_wall_paint_quantity


def _room_has_wall_tile(room: QuantityRow) -> bool:
    name = room.room_name
    return any(keyword in name for keyword in ["\u53a8\u623f", "\u536b", "\u6d17\u624b\u95f4", "\u536b\u751f\u95f4", "\u9732\u53f0", "\u9633\u53f0"])


def _is_section_row(number: Any, sheet, row_index: int) -> bool:
    return isinstance(number, str) and _as_text(sheet.cell(row=row_index, column=2).value) is not None


def _is_skip_row(name: str) -> bool:
    return name.strip().replace(" ", "") in {"\u5c0f\u8ba1"} or name.startswith("\u7f16\u5236\u8bf4\u660e")


def _is_space_template_section(name: str) -> bool:
    if any(keyword in name for keyword in _NON_SPACE_SECTION_KEYWORDS):
        return False
    return any(keyword in name for keyword in _SPACE_TEMPLATE_KEYWORDS)


def _section_label(index: int) -> str:
    if index <= len(_SECTION_NUMERALS):
        return _SECTION_NUMERALS[index - 1]
    return str(index)


def _round_quantity(value: float) -> float:
    return round(value, 6)


def _number_or_zero(value: Any) -> float | int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return value
    return float(value)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
