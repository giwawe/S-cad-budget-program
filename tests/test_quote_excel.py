from pathlib import Path

from openpyxl import Workbook, load_workbook

from cad_budget.models import DataStatus, HeightMode, QuantityRow, QuantityResult, SpaceType
from cad_budget.quote_excel import export_residential_quote, parse_quote_template


def test_parse_quote_template_reads_fitout_sheet_and_ignores_half_package(tmp_path: Path):
    template_path = tmp_path / "template.xlsx"
    _create_quote_template(template_path)

    template = parse_quote_template(template_path)

    assert template.sheet_name == "\u6574\u88c5"
    assert [section.name for section in template.sections] == [
        "\u5ba2\u5385\u5de5\u7a0b",
        "\u53a8\u623f\u5de5\u7a0b",
        "\u5176\u4ed6\u5de5\u7a0b",
    ]
    assert template.sections[0].items[0].name == "\u9876\u9762\u6279\u5d4c"
    assert template.sections[0].items[0].labor_price == 10
    assert all(item.name != "\u534a\u5305\u9879\u76ee" for section in template.sections for item in section.items)


def test_export_residential_quote_generates_actual_room_sections_and_preserves_manual_items(tmp_path: Path):
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "quote.xlsx"
    _create_quote_template(template_path)
    result = QuantityResult(
        project_name="Quote Demo",
        rows=[
            _quantity_row("living", "\u5ba2\u5385", floor_area=20.0, net_wall_area=50.0),
            _quantity_row("kitchen", "\u53a8\u623f", floor_area=6.0, net_wall_area=18.0),
            _quantity_row("bath", "\u4e3b\u536b", floor_area=3.0, net_wall_area=15.0),
        ],
        exceptions=[],
    )

    export_residential_quote(result, template_path, output_path)

    workbook = load_workbook(output_path, data_only=False)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    assert workbook.sheetnames == ["\u5546\u54c1\u623f\u6574\u88c5\u62a5\u4ef7"]
    assert _row_containing(rows, "\u5ba2\u5385\u5de5\u7a0b") is not None
    assert _row_containing(rows, "\u53a8\u623f\u5de5\u7a0b") is not None
    assert _row_containing(rows, "\u4e3b\u536b\u5de5\u7a0b") is not None

    living_wall_paint = _row_containing(rows, "\u5899\u9762\u4e73\u80f6\u6f06")
    assert living_wall_paint[3] == 50.0
    assert living_wall_paint[4:7] == (10, 0, 10)

    kitchen_floor_tile = _row_containing_after(rows, "\u53a8\u623f\u5de5\u7a0b", "\u5730\u9762\u7816\u94fa\u8d34(750X1500)")
    assert kitchen_floor_tile[3] == 6.0

    bath_waterproof = _row_containing_after(rows, "\u4e3b\u536b\u5de5\u7a0b", "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406")
    assert bath_waterproof[3] == 18.0

    manual_item = _row_containing(rows, "\u5783\u573e\u6e05\u8fd0\u8d39")
    assert manual_item[3] == 99
    assert manual_item[7].startswith("=D")

    assert _row_containing(rows, "\u76f4\u63a5\u8d39\u5408\u8ba1") is not None
    assert _row_containing(rows, "\u5de5\u7a0b\u7ba1\u7406\u8d39") is not None
    assert _row_containing(rows, "\u5de5\u7a0b\u603b\u9020\u4ef7") is not None


def test_export_residential_quote_uses_one_wall_tile_variant_for_wet_rooms(tmp_path: Path):
    template_path = tmp_path / "template.xlsx"
    output_path = tmp_path / "quote.xlsx"
    _create_quote_template(template_path, include_both_wall_tile_variants=True)
    result = QuantityResult(
        project_name="Wet Room Demo",
        rows=[_quantity_row("kitchen", "\u53a8\u623f", floor_area=6.0, net_wall_area=18.0)],
        exceptions=[],
    )

    export_residential_quote(result, template_path, output_path)

    workbook = load_workbook(output_path, data_only=False)
    rows = list(workbook.active.iter_rows(values_only=True))
    kitchen_rows = _rows_between_section_and_subtotal(rows, "\u53a8\u623f\u5de5\u7a0b")
    tile_rows = [row for row in kitchen_rows if row[1] in {"\u5899\u9762\u8d34\u74f7\u7816(600x1200)", "\u5899\u9762\u8d34\u74f7\u7816(600X1200)"}]
    assert len(tile_rows) == 1
    assert tile_rows[0][3] == 18.0


def _create_quote_template(path: Path, *, include_both_wall_tile_variants: bool = False) -> None:
    workbook = Workbook()
    half = workbook.active
    half.title = "\u534a\u5305"
    _write_quote_header(half)
    half.append(["\u4e00", "\u534a\u5305\u5de5\u7a0b"])
    half.append([1, "\u534a\u5305\u9879\u76ee", "M2", 1, 2, 3, 4, "=D6*(E6+F6+G6)", "\u4e0d\u5e94\u8bfb\u53d6"])

    fitout = workbook.create_sheet("\u6574\u88c5")
    _write_quote_header(fitout)
    fitout.append(["\u4e00", "\u5ba2\u5385\u5de5\u7a0b"])
    fitout.append([1, "\u9876\u9762\u6279\u5d4c", "M2", 26.8, 0, 15, 10, None, "\u9876\u9762\u8bf4\u660e"])
    fitout.append([2, "\u9876\u9762\u4e73\u80f6\u6f06", "M2", 26.8, 10, 0, 10, None, "\u9876\u6f06\u8bf4\u660e"])
    fitout.append([3, "\u5899\u9762\u754c\u9762\u5242\u5904\u7406", "M2", 52.15, 0, 4, 3, None, "\u754c\u9762\u5242\u8bf4\u660e"])
    fitout.append([4, "\u5899\u9762\u6279\u5d4c", "M2", 52.15, 0, 15, 10, None, "\u5899\u6279\u8bf4\u660e"])
    fitout.append([5, "\u5899\u9762\u4e73\u80f6\u6f06", "M2", 52.15, 10, 0, 10, None, "\u5899\u6f06\u8bf4\u660e"])
    fitout.append([6, "\u5730\u9762\u7816\u94fa\u8d34(750X1500)", "M2", 26.8, 0, 36, 60, None, "\u5730\u7816\u8bf4\u660e"])
    fitout.append([None, "\u5c0f \u8ba1", None, None, None, None, None, "=SUM(H6:H11)"])
    fitout.append(["\u4e8c", "\u53a8\u623f\u5de5\u7a0b"])
    fitout.append([1, "\u5730\u9762\u627e\u5e73", "M2", 2.6, 0, 26, 30, None, "\u627e\u5e73\u8bf4\u660e"])
    fitout.append([2, "\u5899\u5730\u9762\u9632\u6f0f\u5904\u7406", "M2", 6.6, 28, 10.5, 13, None, "\u9632\u6c34\u8bf4\u660e"])
    fitout.append([3, "\u5899\u9762\u8d34\u74f7\u7816(600X1200)", "M2", 17.7, 0, 40, 60, None, "\u5899\u7816\u8bf4\u660e"])
    fitout.append([4, "\u5730\u9762\u7816\u94fa\u8d34(750X1500)", "M2", 6.6, 0, 36, 60, None, "\u5730\u7816\u8bf4\u660e"])
    if include_both_wall_tile_variants:
        fitout.append([5, "\u5899\u9762\u8d34\u74f7\u7816(600x1200)", "M2", 17.7, 0, 40, 60, None, "\u5899\u7816\u8bf4\u660e"])
    fitout.append([None, "\u5c0f \u8ba1", None, None, None, None, None, "=SUM(H14:H17)"])
    fitout.append(["\u4e09", "\u5176\u4ed6\u5de5\u7a0b"])
    fitout.append([1, "\u5783\u573e\u6e05\u8fd0\u8d39", "M2", 99, 0, 0, 10, None, "\u4eba\u5de5\u6e05\u8fd0"])
    fitout.append([None, "\u5c0f \u8ba1", None, None, None, None, None, "=SUM(H20:H20)"])
    fitout.append(["A", "\u76f4\u63a5\u8d39\u5408\u8ba1(\u4e00+\u2026...\u5341)", None, None, None, None, None, "=H12+H18+H21"])
    fitout.append(["B", "\u5de5\u7a0b\u7ba1\u7406\u8d39(D=A* 5%)", None, None, None, None, None, "=H22*0.05"])
    fitout.append(["C", "\u7a0e\u91d1E=(A+B)* 3%", None, None, None, None, None, 0])
    fitout.append(["D", "\u5de5\u7a0b\u603b\u9020\u4ef7F=(A+B+C)", None, None, None, None, None, "=SUM(H22:H24)"])
    workbook.save(path)


def _write_quote_header(sheet) -> None:
    sheet.append(["\u5de5\u7a0b(\u9884) \u7b97\u8868"])
    sheet.append(["\u540d\u79f0\uff1aDemo"])
    sheet.append([
        "\u7f16\u53f7",
        "\u9879\u76ee\u540d\u79f0",
        "\u5355\u4f4d",
        "\u6570\u91cf",
        "\u6750\u6599\u8d39(\u5143)",
        None,
        "\u4eba\u5de5\u8d39\n(\u5143)",
        "\u603b\u4ef7(\u5143)",
        "\u6750  \u6599  \u53ca  \u5de5  \u827a  \u8bf4  \u660e",
    ])
    sheet.append([None, None, None, None, "\u4e3b\u6750\n\u5355\u4ef7", "\u8f85\u6750\n\u5355\u4ef7"])


def _quantity_row(room_id: str, name: str, *, floor_area: float, net_wall_area: float) -> QuantityRow:
    return QuantityRow(
        room_id=room_id,
        floor=None,
        room_name=name,
        space_type=SpaceType.NORMAL,
        height=2.8,
        height_mode=HeightMode.PROJECT_DEFAULT,
        floor_area=floor_area,
        floor_perimeter=0,
        wall_measure_perimeter=0,
        open_boundary_length=0,
        gross_wall_area=net_wall_area,
        window_count=0,
        window_area=0,
        door_opening_count=0,
        door_opening_area=0,
        net_wall_area=net_wall_area,
        is_outdoor=False,
        include_in_floor_quantity=True,
        include_in_wall_paint_quantity=True,
        status=DataStatus.CONFIRMED,
    )


def _row_containing(rows, text: str):
    for row in rows:
        if any(text in cell for cell in row if isinstance(cell, str)):
            return row
    return None


def _row_containing_after(rows, section_name: str, item_name: str):
    section_seen = False
    for row in rows:
        if any(section_name in cell for cell in row if isinstance(cell, str)):
            section_seen = True
            continue
        if section_seen and any(item_name in cell for cell in row if isinstance(cell, str)):
            return row
    return None


def _rows_between_section_and_subtotal(rows, section_name: str):
    section_seen = False
    result = []
    for row in rows:
        if any(section_name in cell for cell in row if isinstance(cell, str)):
            section_seen = True
            continue
        if section_seen and row[1] == "\u5c0f \u8ba1":
            return result
        if section_seen:
            result.append(row)
    return result
