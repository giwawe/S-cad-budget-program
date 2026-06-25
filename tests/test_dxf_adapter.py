from math import cos, radians, sin
from pathlib import Path

import ezdxf
import pytest

from cad_budget.cad_adapter_models import CadImportOptions, CadUnit
from cad_budget.dxf_adapter import import_dxf
from cad_budget.models import ConstructionKind, FixtureKind, LayerName
from cad_budget.quantity import calculate_quantities


def _save_doc(path: Path, doc: ezdxf.EzDxf) -> Path:
    doc.saveas(path)
    return path


def test_import_dxf_reads_closed_room_and_text(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_TEXT")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("卧室", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    dxf_path = _save_doc(tmp_path / "apartment.dxf", doc)

    result = import_dxf(
        CadImportOptions(
            source_path=dxf_path,
            confirmed_unit=CadUnit.MILLIMETER,
            project_name_override="Apartment",
        )
    )

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.project_name == "Apartment"
    assert len(result.project.rooms) == 1
    assert result.project.rooms[0].name == "卧室"
    assert result.project.rooms[0].points[1].x == 4
    assert result.project.rooms[0].points[2].y == 3


def test_import_dxf_filters_unlabeled_room_candidates_when_quote_text_matches_rooms(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_TEXT")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(6000, 0), (9000, 0), (9000, 2000), (6000, 2000), (6000, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("卧室", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    dxf_path = _save_doc(tmp_path / "extra_unlabeled_room_candidate.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.rooms) == 1
    assert result.project.rooms[0].name == "卧室"
    assert any(
        issue.code == "ROOM_BOUNDARY_WITHOUT_TEXT_IGNORED" and issue.entity_id is not None
        for issue in result.issues
    )


def test_import_dxf_uses_ordinary_text_when_quote_text_layer_is_absent(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("A-ROOM-NAME")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Bedroom", dxfattribs={"layer": "A-ROOM-NAME", "height": 250}).set_placement((1500, 1200))
    dxf_path = _save_doc(tmp_path / "ordinary_text_name.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.texts) == 1
    assert result.project.rooms[0].name == "Bedroom"


def test_import_dxf_prefers_quote_text_over_ordinary_text(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_TEXT")
    doc.layers.add("A-ROOM-NAME")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Bedroom", dxfattribs={"layer": "A-ROOM-NAME", "height": 250}).set_placement((1500, 1200))
    modelspace.add_text("Primary Bedroom", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1600, 1300))
    dxf_path = _save_doc(tmp_path / "quote_text_preferred.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.texts) == 1
    assert result.project.texts[0].text == "Primary Bedroom"
    assert result.project.rooms[0].name == "Primary Bedroom"


def test_import_dxf_blocks_when_quote_room_is_missing(tmp_path: Path):
    doc = ezdxf.new("R2010")
    dxf_path = _save_doc(tmp_path / "empty.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert result.has_blockers
    assert result.issues[0].code == "QUOTE_ROOM_MISSING"


def test_import_dxf_blocks_self_intersecting_room_boundary(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 3000), (0, 3000), (4000, 0), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "bowtie_room.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert result.has_blockers
    assert any(issue.code == "ROOM_BOUNDARY_INVALID" for issue in result.issues)


def test_import_dxf_blocks_open_quote_room_without_dropping_valid_rooms(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(5000, 0), (7000, 0), (7000, 2000), (5000, 2000)],
        dxfattribs={"layer": "QUOTE_ROOM"},
    )
    dxf_path = _save_doc(tmp_path / "open_quote_room.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert result.has_blockers
    assert result.project is not None
    assert len(result.project.rooms) == 1
    issue = next(issue for issue in result.issues if issue.code == "ROOM_BOUNDARY_INVALID")
    assert issue.entity_id is not None
    assert issue.layer == "QUOTE_ROOM"


def test_import_dxf_accepts_room_boundary_when_first_and_last_points_match_without_closed_flag(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM"},
    )
    dxf_path = _save_doc(tmp_path / "visually_closed_room.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.rooms) == 1
    assert result.project.rooms[0].points[0] == result.project.rooms[0].points[-1]


def test_import_dxf_snaps_room_boundary_closed_when_gap_is_within_one_millimeter(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0.5)],
        dxfattribs={"layer": "QUOTE_ROOM"},
    )
    dxf_path = _save_doc(tmp_path / "nearly_closed_room.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.rooms) == 1
    assert result.project.rooms[0].points[0] == result.project.rooms[0].points[-1]


def test_import_dxf_blocks_when_file_cannot_be_read(tmp_path: Path):
    bad_path = tmp_path / "bad.dxf"
    bad_path.write_text("not a dxf", encoding="utf-8")

    result = import_dxf(CadImportOptions(source_path=bad_path))

    assert result.has_blockers
    assert result.issues[0].code == "DXF_READ_FAILED"


def test_import_dxf_blocks_when_file_unit_conflicts_with_confirmed_unit(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4, 0), (4, 3), (0, 3), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "meters.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert result.has_blockers
    assert any(issue.code == "CAD_UNIT_CONFLICT" for issue in result.issues)


def test_import_dxf_blocks_when_large_coordinate_meter_unit_conflicts_with_confirmed_unit(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "large-meter-header.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert result.has_blockers
    assert any(issue.code == "CAD_UNIT_CONFLICT" for issue in result.issues)


def test_import_dxf_reads_window_outline_door_wall_and_opening(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_WINDOW", "QUOTE_DOOR", "QUOTE_WALL", "QUOTE_OPENING"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, -100), (2500, -100), (2500, 100), (1000, 100), (1000, -100)],
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(3000, 0), (3900, 0)],
        dxfattribs={"layer": "QUOTE_DOOR"},
    )
    modelspace.add_lwpolyline(
        [(0, 0), (5000, 0)],
        dxfattribs={"layer": "QUOTE_WALL"},
    )
    modelspace.add_lwpolyline(
        [(5000, 1000), (5000, 2200)],
        dxfattribs={"layer": "QUOTE_OPENING"},
    )
    dxf_path = _save_doc(tmp_path / "openings.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.5
    assert result.project.windows[0].height is None
    assert result.project.windows[0].attributes["source"] == "closed_outline"
    assert len(result.project.doors) == 1
    assert result.project.doors[0].width == 0.9
    assert len(result.project.walls) == 1
    assert len(result.project.openings) == 1


def test_import_dxf_reads_line_wall_geometry(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WALL")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_line((0, 0), (4000, 0), dxfattribs={"layer": "QUOTE_WALL"})
    dxf_path = _save_doc(tmp_path / "line_wall.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.walls) == 1
    assert result.project.walls[0].points[1].x == 4


def test_imports_quote_custom_and_cabinet_lines(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_CUSTOM", "QUOTE_CABINET"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("涓诲崸", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_line((500, 500), (2500, 500), dxfattribs={"layer": "QUOTE_CUSTOM"})
    modelspace.add_line((500, 900), (3500, 900), dxfattribs={"layer": "QUOTE_CABINET"})
    dxf_path = _save_doc(tmp_path / "fixtures.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.custom_items) == 1
    assert result.project.custom_items[0].length == 2.0
    assert result.project.custom_items[0].kind is FixtureKind.CUSTOM
    assert len(result.project.cabinet_items) == 1
    assert result.project.cabinet_items[0].length == 3.0
    assert result.project.cabinet_items[0].kind is FixtureKind.CABINET


def test_imports_fixture_xdata_attributes(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.add("CAD_BUDGET")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_CUSTOM", "QUOTE_CABINET"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("主卧", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    custom = modelspace.add_line((500, 500), (2500, 500), dxfattribs={"layer": "QUOTE_CUSTOM"})
    custom.set_xdata(
        "CAD_BUDGET",
        [(1000, "HEIGHT=2400"), (1000, "TYPE=衣柜"), (1000, "ROOM=主卧"), (1000, "ROOM_ID=bedroom")],
    )
    cabinet = modelspace.add_line((500, 900), (3500, 900), dxfattribs={"layer": "QUOTE_CABINET"})
    cabinet.set_xdata("CAD_BUDGET", [(1000, "TYPE=地柜"), (1000, "ROOM=厨房")])
    dxf_path = _save_doc(tmp_path / "fixture-xdata.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert not result.has_blockers
    assert result.project is not None
    custom_item = result.project.custom_items[0]
    assert custom_item.height == 2.4
    assert custom_item.fixture_type == "衣柜"
    assert custom_item.room_id == "bedroom"
    assert custom_item.attributes["ROOM"] == "主卧"
    cabinet_item = result.project.cabinet_items[0]
    assert cabinet_item.fixture_type == "地柜"
    assert cabinet_item.attributes["ROOM"] == "厨房"


def test_imports_base_and_wall_cabinet_layers_as_typed_cabinet_markers(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_BASE_CABINET", "QUOTE_WALL_CABINET"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("厨房", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_line((500, 900), (3500, 900), dxfattribs={"layer": "QUOTE_BASE_CABINET"})
    modelspace.add_line((500, 900), (3500, 900), dxfattribs={"layer": "QUOTE_WALL_CABINET"})
    dxf_path = _save_doc(tmp_path / "typed-cabinets.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.cabinet_items) == 2
    assert [item.layer for item in result.project.cabinet_items] == [
        LayerName.QUOTE_BASE_CABINET,
        LayerName.QUOTE_WALL_CABINET,
    ]
    assert [item.kind for item in result.project.cabinet_items] == [FixtureKind.CABINET, FixtureKind.CABINET]
    assert [item.length for item in result.project.cabinet_items] == [3.0, 3.0]
    assert [item.fixture_type for item in result.project.cabinet_items] == ["地柜", "吊柜"]


def test_imports_closed_custom_outline_using_longest_rectangle_edge(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_CUSTOM"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("瀹㈠巺", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_lwpolyline(
        [(500, 500), (2500, 500), (2500, 1100), (500, 1100), (500, 500)],
        dxfattribs={"layer": "QUOTE_CUSTOM", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "custom-outline.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.custom_items) == 1
    assert result.project.custom_items[0].length == 2.0


def test_import_dxf_reads_insert_door_width_from_block_scale(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("door_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_DOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_blockref(
        "door_block",
        (2000, 0),
        dxfattribs={"layer": "QUOTE_DOOR", "xscale": 900, "yscale": -900},
    )
    dxf_path = _save_doc(tmp_path / "insert_door.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.doors) == 1
    assert result.project.doors[0].point.x == 2
    assert result.project.doors[0].width == 0.9
    assert result.project.doors[0].attributes["source"] == "insert"


def test_import_dxf_reads_insert_door_width_and_height_attributes(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("door_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_DOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("door_block", (2000, 0), dxfattribs={"layer": "QUOTE_DOOR"})
    insert.add_attrib("WIDTH", "900")
    insert.add_attrib("HEIGHT", "2100")
    dxf_path = _save_doc(tmp_path / "insert_door_attrs.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.doors) == 1
    assert result.project.doors[0].width == 0.9
    assert result.project.doors[0].height == 2.1
    assert result.project.doors[0].attributes["source"] == "insert_attributes"


def test_import_dxf_reads_chinese_insert_door_attributes(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("door_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_DOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("door_block", (2000, 0), dxfattribs={"layer": "QUOTE_DOOR"})
    insert.add_attrib("门宽", "900")
    insert.add_attrib("门高", "2100")
    dxf_path = _save_doc(tmp_path / "insert_door_chinese_attrs.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.doors) == 1
    assert result.project.doors[0].width == 0.9
    assert result.project.doors[0].height == 2.1


def test_import_dxf_accepts_window_outline_when_first_and_last_points_match_without_closed_flag(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, -100), (2500, -100), (2500, 100), (1000, 100), (1000, -100)],
        dxfattribs={"layer": "QUOTE_WINDOW"},
    )
    dxf_path = _save_doc(tmp_path / "visually_closed_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.5


def test_import_dxf_reads_window_insert_width_and_height_attributes(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("window_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("window_block", (2000, 0), dxfattribs={"layer": "QUOTE_WINDOW"})
    insert.add_attrib("WIDTH", "1200")
    insert.add_attrib("HEIGHT", "1500")
    dxf_path = _save_doc(tmp_path / "window_insert_attrs.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.2
    assert result.project.windows[0].height == 1.5
    assert result.project.windows[0].attributes["source"] == "insert_attributes"


def test_import_dxf_reads_chinese_window_insert_attributes(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("window_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("window_block", (2000, 0), dxfattribs={"layer": "QUOTE_WINDOW"})
    insert.add_attrib("窗宽", "1200")
    insert.add_attrib("窗高", "1500")
    dxf_path = _save_doc(tmp_path / "window_insert_chinese_attrs.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.2
    assert result.project.windows[0].height == 1.5


def test_import_dxf_treats_small_window_attribute_values_as_meters(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("window_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("window_block", (2000, 0), dxfattribs={"layer": "QUOTE_WINDOW"})
    insert.add_attrib("width", "1.2")
    insert.add_attrib("height", "1.5")
    dxf_path = _save_doc(tmp_path / "window_insert_meter_attrs.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.2
    assert result.project.windows[0].height == 1.5


def test_import_dxf_imports_window_insert_width_without_height(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("window_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("window_block", (2000, 0), dxfattribs={"layer": "QUOTE_WINDOW"})
    insert.add_attrib("WIDTH", "1200")
    dxf_path = _save_doc(tmp_path / "window_insert_width_only.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.windows) == 1
    assert result.project.windows[0].width == 1.2
    assert result.project.windows[0].height is None


def test_import_dxf_warns_for_window_insert_without_parseable_width(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("window_block")
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    insert = modelspace.add_blockref("window_block", (2000, 0), dxfattribs={"layer": "QUOTE_WINDOW"})
    insert.add_attrib("WIDTH", "wide")
    dxf_path = _save_doc(tmp_path / "window_insert_bad_width.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows == []
    assert any(issue.code == "WINDOW_WIDTH_ATTRIBUTE_INVALID" for issue in result.issues)


def test_import_dxf_reads_height_void_exterior_and_building_area_layers(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in [
        "QUOTE_ROOM",
        "QUOTE_HEIGHT",
        "QUOTE_VOID",
        "QUOTE_EXT_WALL",
        "QUOTE_EXT_OPENING",
        "QUOTE_BUILDING_AREA",
    ]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("3.6", dxfattribs={"layer": "QUOTE_HEIGHT", "height": 250}).set_placement((100, 100))
    modelspace.add_lwpolyline(
        [(1000, 1000), (2500, 1000), (2500, 2200), (1000, 2200), (1000, 1000)],
        dxfattribs={"layer": "QUOTE_VOID", "closed": True},
    )
    modelspace.add_lwpolyline([(0, -200), (4000, -200)], dxfattribs={"layer": "QUOTE_EXT_WALL"})
    modelspace.add_lwpolyline([(1200, -200), (2200, -200)], dxfattribs={"layer": "QUOTE_EXT_OPENING"})
    modelspace.add_lwpolyline(
        [(-200, -200), (4200, -200), (4200, 3200), (-200, 3200), (-200, -200)],
        dxfattribs={"layer": "QUOTE_BUILDING_AREA", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "special_layers.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.heights) == 1
    assert result.project.heights[0].height == 3.6
    assert len(result.project.voids) == 1
    assert len(result.project.exterior_walls) == 1
    assert len(result.project.exterior_openings) == 1
    assert len(result.project.building_areas) == 1
    assert calculate_quantities(result.project).building_area == 14.96


def test_import_dxf_reads_exterior_wall_quote_include_xdata(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_BUDGET")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_EXT_WALL"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Room", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    ext_wall = modelspace.add_lwpolyline([(0, -200), (4000, -200)], dxfattribs={"layer": "QUOTE_EXT_WALL"})
    ext_wall.set_xdata("CAD_BUDGET", [(1000, "QUOTE_INCLUDE=false")])
    dxf_path = _save_doc(tmp_path / "exterior_include_xdata.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.exterior_walls[0].attributes["include_in_quote"] is False
    quantity = calculate_quantities(result.project)
    assert quantity.exterior_rows[0].include_in_quote is False


def test_import_dxf_reads_construction_marker_layers_and_xdata(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_BUDGET")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_DEMO_WALL", "QUOTE_NEW_WALL", "QUOTE_LINTEL", "QUOTE_LINTEL_HOLE"]:
        doc.layers.add(layer)

    modelspace.add_lwpolyline(
        [(-1000, -1000), (4000, -1000), (4000, 4000), (-1000, 4000), (-1000, -1000)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Room", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    demo = modelspace.add_lwpolyline([(0, 0), (3000, 0)], dxfattribs={"layer": "QUOTE_DEMO_WALL"})
    demo.set_xdata("CAD_BUDGET", [(1000, "HEIGHT=2600")])
    new_wall = modelspace.add_lwpolyline([(0, 1000), (2000, 1000)], dxfattribs={"layer": "QUOTE_NEW_WALL"})
    new_wall.set_xdata("CAD_BUDGET", [(1000, "HEIGHT=2800"), (1000, "THICKNESS=120")])
    modelspace.add_lwpolyline([(0, 2000), (1000, 2000)], dxfattribs={"layer": "QUOTE_LINTEL"})
    modelspace.add_point((0, 3000), dxfattribs={"layer": "QUOTE_LINTEL_HOLE"})
    dxf_path = _save_doc(tmp_path / "construction_markers.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.demo_walls[0].kind is ConstructionKind.DEMO_WALL
    assert result.project.demo_walls[0].height == 2.6
    assert result.project.demo_walls[0].length == 3.0
    assert result.project.new_walls[0].kind is ConstructionKind.NEW_WALL
    assert result.project.new_walls[0].height == 2.8
    assert result.project.new_walls[0].thickness == 0.12
    assert result.project.lintels[0].kind is ConstructionKind.LINTEL
    assert result.project.lintel_holes[0].kind is ConstructionKind.LINTEL_HOLE


def test_import_dxf_reads_wall_tile_marker_layer_and_height(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_BUDGET")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_WALL_TILE"]:
        doc.layers.add(layer)

    modelspace.add_lwpolyline(
        [(-1000, -1000), (4000, -1000), (4000, 4000), (-1000, 4000), (-1000, -1000)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("阳台", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    wall_tile = modelspace.add_lwpolyline([(0, 0), (3000, 0)], dxfattribs={"layer": "QUOTE_WALL_TILE"})
    wall_tile.set_xdata("CAD_BUDGET", [(1000, "HEIGHT=1200")])
    dxf_path = _save_doc(tmp_path / "wall_tile_marker.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path, confirmed_unit=CadUnit.MILLIMETER))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.wall_tiles) == 1
    assert result.project.wall_tiles[0].kind is ConstructionKind.WALL_TILE
    assert result.project.wall_tiles[0].height == 1.2
    quantity = calculate_quantities(result.project)
    details = {detail.id: detail for detail in quantity.construction_details}
    assert details[result.project.wall_tiles[0].id].area == 3.6


def test_import_dxf_reads_pipe_marker_layers_and_heights(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_BUDGET")
    doc.blocks.new("pipe_block")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_PIPE_INSULATION", "QUOTE_PIPE_WRAP"]:
        doc.layers.add(layer)

    modelspace.add_lwpolyline(
        [(-1000, -1000), (4000, -1000), (4000, 4000), (-1000, 4000), (-1000, -1000)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Room", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    insulation = modelspace.add_point((0, 0), dxfattribs={"layer": "QUOTE_PIPE_INSULATION"})
    insulation.set_xdata("CAD_BUDGET", [(1000, "HEIGHT=2400")])
    pipe_wrap = modelspace.add_blockref("pipe_block", (1000, 0), dxfattribs={"layer": "QUOTE_PIPE_WRAP"})
    pipe_wrap.add_attrib("HEIGHT", "2.1")
    dxf_path = _save_doc(tmp_path / "pipe_markers.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.pipe_insulations[0].kind is ConstructionKind.PIPE_INSULATION
    assert result.project.pipe_insulations[0].height == 2.4
    assert result.project.pipe_wraps[0].kind is ConstructionKind.PIPE_WRAP
    assert result.project.pipe_wraps[0].height == 2.1
    quantity = calculate_quantities(result.project)
    details = {detail.id: detail for detail in quantity.construction_details}
    assert details[result.project.pipe_insulations[0].id].length == 2.4
    assert details[result.project.pipe_wraps[0].id].length == 2.1


def test_import_dxf_reads_exterior_repair_markers_as_area_or_heighted_line(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_BUDGET")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_TEXT", "QUOTE_EXT_REPAIR"]:
        doc.layers.add(layer)

    modelspace.add_lwpolyline(
        [(-1000, -1000), (5000, -1000), (5000, 5000), (-1000, 5000), (-1000, -1000)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("Room", dxfattribs={"layer": "QUOTE_TEXT", "height": 250}).set_placement((1500, 1200))
    modelspace.add_lwpolyline(
        [(0, 0), (2000, 0), (2000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_EXT_REPAIR", "closed": True},
    )
    repair_line = modelspace.add_line((3000, 0), (5000, 0), dxfattribs={"layer": "QUOTE_EXT_REPAIR"})
    repair_line.set_xdata("CAD_BUDGET", [(1000, "HEIGHT=1500")])
    dxf_path = _save_doc(tmp_path / "exterior_repair_markers.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.exterior_repairs) == 2
    assert {marker.kind for marker in result.project.exterior_repairs} == {ConstructionKind.EXTERIOR_REPAIR}
    quantity = calculate_quantities(result.project)
    details = {detail.id: detail for detail in quantity.construction_details}
    assert details[result.project.exterior_repairs[0].id].area == 6.0
    assert details[result.project.exterior_repairs[1].id].area == 3.0


def test_import_dxf_assigns_room_floor_from_quote_floor_text(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_FLOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("2F", dxfattribs={"layer": "QUOTE_FLOOR", "height": 250}).set_placement((1500, 1200))
    dxf_path = _save_doc(tmp_path / "floor_marker.dxf", doc)

    result = import_dxf(
        CadImportOptions(
            source_path=dxf_path,
            floor_heights={"2F": 3.2},
        )
    )

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.rooms) == 1
    assert result.project.rooms[0].floor == "2F"
    assert result.project.floor_heights == {"2F": 3.2}


def test_import_dxf_warns_when_room_has_multiple_quote_floor_texts(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_FLOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("1F", dxfattribs={"layer": "QUOTE_FLOOR", "height": 250}).set_placement((1000, 1000))
    modelspace.add_text("2F", dxfattribs={"layer": "QUOTE_FLOOR", "height": 250}).set_placement((2500, 1000))
    dxf_path = _save_doc(tmp_path / "ambiguous_floor_marker.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.rooms[0].floor is None
    assert any(issue.code == "ROOM_FLOOR_AMBIGUOUS" for issue in result.issues)


def test_import_dxf_assigns_room_floor_to_imported_markers(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.blocks.new("door_block")
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_FLOOR", "QUOTE_WINDOW", "QUOTE_DOOR", "QUOTE_WALL", "QUOTE_OPENING", "QUOTE_HEIGHT"]:
        doc.layers.add(layer)
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("2F", dxfattribs={"layer": "QUOTE_FLOOR", "height": 250}).set_placement((1500, 1200))
    modelspace.add_lwpolyline(
        [(1000, -100), (2500, -100), (2500, 100), (1000, 100), (1000, -100)],
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    modelspace.add_blockref(
        "door_block",
        (3000, 0),
        dxfattribs={"layer": "QUOTE_DOOR", "xscale": 900, "yscale": 900},
    )
    modelspace.add_line((0, 0), (4000, 0), dxfattribs={"layer": "QUOTE_WALL"})
    modelspace.add_lwpolyline([(4000, 1000), (4000, 2200)], dxfattribs={"layer": "QUOTE_OPENING"})
    modelspace.add_text("3.2", dxfattribs={"layer": "QUOTE_HEIGHT", "height": 250}).set_placement((3000, 1200))
    dxf_path = _save_doc(tmp_path / "floor_marker_inheritance.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.rooms[0].floor == "2F"
    assert result.project.windows[0].floor == "2F"
    assert result.project.doors[0].floor == "2F"
    assert result.project.walls[0].floor == "2F"
    assert result.project.openings[0].floor == "2F"
    assert result.project.heights[0].floor == "2F"


def test_import_dxf_warns_for_invalid_height_text(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_HEIGHT")
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_text("high", dxfattribs={"layer": "QUOTE_HEIGHT", "height": 250}).set_placement((100, 100))
    dxf_path = _save_doc(tmp_path / "bad_height.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.heights == []
    assert any(issue.code == "HEIGHT_TEXT_INVALID" for issue in result.issues)


def test_import_dxf_infers_polygon_window_width_from_extents(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, -100), (2200, -150), (2600, 0), (2200, 150), (1000, 100), (1000, -100)],
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "polygon_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows[0].width == 1.6


def test_import_dxf_flattens_arc_based_window_outline(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, 0, 0.5), (2000, 0, 0), (2000, 200, 0), (1000, 200, 0), (1000, 0, 0)],
        format="xyb",
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "arc_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows[0].width >= 1.0


def test_import_dxf_warns_for_open_window_outline(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, 0), (2000, 0), (2000, 200), (1000, 200)],
        dxfattribs={"layer": "QUOTE_WINDOW"},
    )
    dxf_path = _save_doc(tmp_path / "open_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows == []
    assert any(issue.code == "WINDOW_OUTLINE_NOT_CLOSED" for issue in result.issues)


def test_import_dxf_ignores_window_layer_auxiliary_linework(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, 0), (2000, 0)],
        dxfattribs={"layer": "QUOTE_WINDOW"},
    )
    dxf_path = _save_doc(tmp_path / "window_auxiliary_linework.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows == []
    assert not any(issue.code == "WINDOW_OUTLINE_NOT_CLOSED" for issue in result.issues)


def test_import_dxf_infers_closed_door_outline_width_and_centroid(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_DOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, -100), (1900, -100), (1900, 100), (1000, 100), (1000, -100)],
        dxfattribs={"layer": "QUOTE_DOOR", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "door_outline.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.doors) == 1
    assert result.project.doors[0].width == pytest.approx(0.9)
    assert result.project.doors[0].point.x == pytest.approx(1.45)
    assert result.project.doors[0].point.y == pytest.approx(0.0)


def test_import_dxf_infers_rotated_window_width_from_outline_major_dimension(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    angle = radians(8)
    center_x = 1800
    center_y = 1200
    half_width = 750
    half_depth = 100
    corners = []
    for local_x, local_y in [
        (-half_width, -half_depth),
        (half_width, -half_depth),
        (half_width, half_depth),
        (-half_width, half_depth),
    ]:
        corners.append(
            (
                center_x + local_x * cos(angle) - local_y * sin(angle),
                center_y + local_x * sin(angle) + local_y * cos(angle),
            )
        )
    modelspace.add_lwpolyline(
        [*corners, corners[0]],
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "rotated_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows[0].width == pytest.approx(1.5, abs=0.001)


def test_import_dxf_warns_for_degenerate_closed_window_outline(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_WINDOW")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, 1000), (1500, 1000), (2000, 1000), (1000, 1000)],
        dxfattribs={"layer": "QUOTE_WINDOW", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "degenerate_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows == []
    assert any(issue.code == "WINDOW_OUTLINE_INVALID" for issue in result.issues)


def test_import_dxf_warns_for_degenerate_closed_door_outline(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    doc.layers.add("QUOTE_ROOM")
    doc.layers.add("QUOTE_DOOR")
    modelspace.add_lwpolyline(
        [(0, 0), (6000, 0), (6000, 3000), (0, 3000), (0, 0)],
        dxfattribs={"layer": "QUOTE_ROOM", "closed": True},
    )
    modelspace.add_lwpolyline(
        [(1000, 1000), (1500, 1000), (2000, 1000), (1000, 1000)],
        dxfattribs={"layer": "QUOTE_DOOR", "closed": True},
    )
    dxf_path = _save_doc(tmp_path / "degenerate_door.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.doors == []
    assert any(issue.code == "DOOR_OUTLINE_INVALID" for issue in result.issues)
