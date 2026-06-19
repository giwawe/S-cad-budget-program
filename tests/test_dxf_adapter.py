from pathlib import Path

import ezdxf

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
