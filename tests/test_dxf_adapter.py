from math import cos, radians, sin
from pathlib import Path

import ezdxf
import pytest

from cad_budget.cad_adapter_models import CadImportOptions, CadUnit
from cad_budget.dxf_adapter import import_dxf


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


def test_import_dxf_blocks_when_quote_room_is_missing(tmp_path: Path):
    doc = ezdxf.new("R2010")
    dxf_path = _save_doc(tmp_path / "empty.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert result.has_blockers
    assert result.issues[0].code == "QUOTE_ROOM_MISSING"


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


def test_import_dxf_reads_height_void_and_exterior_layers(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    modelspace = doc.modelspace()
    for layer in ["QUOTE_ROOM", "QUOTE_HEIGHT", "QUOTE_VOID", "QUOTE_EXT_WALL", "QUOTE_EXT_OPENING"]:
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
    dxf_path = _save_doc(tmp_path / "special_layers.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert len(result.project.heights) == 1
    assert result.project.heights[0].height == 3.6
    assert len(result.project.voids) == 1
    assert len(result.project.exterior_walls) == 1
    assert len(result.project.exterior_openings) == 1


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
        [(1000, 0), (2000, 0)],
        dxfattribs={"layer": "QUOTE_WINDOW"},
    )
    dxf_path = _save_doc(tmp_path / "open_window.dxf", doc)

    result = import_dxf(CadImportOptions(source_path=dxf_path))

    assert not result.has_blockers
    assert result.project is not None
    assert result.project.windows == []
    assert any(issue.code == "WINDOW_OUTLINE_NOT_CLOSED" for issue in result.issues)


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
