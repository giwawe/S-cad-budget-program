# CAD Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first CAD Adapter that imports DXF directly, converts DWG through a configured converter, and emits the existing `ProjectInput` JSON contract for the quantity engine.

**Architecture:** Keep CAD parsing outside the quantity engine. Add a focused adapter layer that reads CAD entities from `QUOTE_*` layers, validates units and severe/minor issues, and writes `ProjectInput`. The CLI gets a new `import-cad` command so users can run `DWG/DXF -> ProjectInput JSON -> calculate`.

**Tech Stack:** Python 3.11, `ezdxf` for DXF parsing, Pydantic models, Typer CLI, existing Shapely-backed quantity engine and pytest test suite.

---

## File Structure

- Create `src/cad_budget/cad_adapter_models.py`
  - Adapter-specific models: `AdapterSeverity`, `AdapterIssue`, `CadUnit`, `CadImportOptions`, `CadImportResult`.
  - Keeps CAD import status separate from quantity result exceptions.

- Create `src/cad_budget/dxf_adapter.py`
  - Reads DXF files with `ezdxf`.
  - Extracts supported `QUOTE_*` entities into `ProjectInput`.
  - Handles unit conversion, room/text/window/door/wall/opening/height/void/exterior layers.
  - Infers window width from closed outlines, including rectangles, polygons, and flattened arc-based shapes.

- Create `src/cad_budget/dwg_converter.py`
  - Small wrapper around an externally configured DWG-to-DXF converter.
  - First version does not bundle or reimplement DWG parsing.

- Modify `src/cad_budget/cli.py`
  - Add `import-cad` command.
  - Accept `.dxf` directly.
  - Accept `.dwg` only when a converter command is configured.

- Modify `pyproject.toml`
  - Add `ezdxf>=1.3.4`.

- Create `tests/test_cad_adapter_models.py`
  - Unit/status validation tests.

- Create `tests/test_dxf_adapter.py`
  - Programmatically generate small DXF fixtures with `ezdxf`.
  - Test room boundaries, text matching, windows, doors, wall/opening layers, units, and issues.

- Create `tests/test_dwg_converter.py`
  - Test converter command success/failure without requiring a real converter.

- Modify `tests/test_cli.py`
  - Test `import-cad` DXF success.
  - Test DWG failure without converter.

---

### Task 1: Add Adapter Models and Dependency

**Files:**
- Modify: `pyproject.toml`
- Create: `src/cad_budget/cad_adapter_models.py`
- Test: `tests/test_cad_adapter_models.py`

- [ ] **Step 1: Add the `ezdxf` dependency**

Modify `pyproject.toml` dependencies to include `ezdxf`:

```toml
dependencies = [
  "ezdxf>=1.3.4",
  "openpyxl>=3.1.5",
  "pydantic>=2.8.0",
  "shapely>=2.0.4",
  "typer>=0.12.3"
]
```

- [ ] **Step 2: Write failing adapter model tests**

Create `tests/test_cad_adapter_models.py`:

```python
from pathlib import Path

from cad_budget.cad_adapter_models import (
    AdapterIssue,
    AdapterSeverity,
    CadImportOptions,
    CadUnit,
)


def test_adapter_issue_defaults_to_warning():
    issue = AdapterIssue(code="WINDOW_HEIGHT_DEFAULTED", message="Window height used default")

    assert issue.severity == AdapterSeverity.WARNING
    assert issue.entity_id is None
    assert issue.layer is None


def test_cad_import_options_defaults_for_millimeter_project():
    options = CadImportOptions(source_path=Path("sample.dxf"))

    assert options.project_name == "sample"
    assert options.confirmed_unit == CadUnit.MILLIMETER
    assert options.default_height == 2.8
    assert options.default_window_height == 1.5
```

- [ ] **Step 3: Run model tests and verify they fail**

Run:

```bash
python -m pytest tests/test_cad_adapter_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cad_budget.cad_adapter_models'`.

- [ ] **Step 4: Implement adapter models**

Create `src/cad_budget/cad_adapter_models.py`:

```python
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from cad_budget.models import ProjectInput


class AdapterSeverity(str, Enum):
    BLOCKER = "blocker"
    WARNING = "warning"


class CadUnit(str, Enum):
    MILLIMETER = "mm"
    CENTIMETER = "cm"
    METER = "m"


class AdapterIssue(BaseModel):
    code: str
    message: str
    severity: AdapterSeverity = AdapterSeverity.WARNING
    entity_id: str | None = None
    layer: str | None = None


class CadImportOptions(BaseModel):
    source_path: Path
    confirmed_unit: CadUnit = CadUnit.MILLIMETER
    project_name_override: str | None = None
    default_height: float = 2.8
    default_window_height: float = 1.5
    floor_heights: dict[str, float] = Field(default_factory=dict)
    dwg_converter_command: list[str] | None = None

    @computed_field
    @property
    def project_name(self) -> str:
        if self.project_name_override:
            return self.project_name_override
        return self.source_path.stem


class CadImportResult(BaseModel):
    project: ProjectInput | None = None
    issues: list[AdapterIssue] = Field(default_factory=list)
    source_path: Path
    dxf_path: Path | None = None

    @property
    def has_blockers(self) -> bool:
        return any(issue.severity == AdapterSeverity.BLOCKER for issue in self.issues)
```

- [ ] **Step 5: Run model tests and verify they pass**

Run:

```bash
python -m pytest tests/test_cad_adapter_models.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/cad_budget/cad_adapter_models.py tests/test_cad_adapter_models.py
git commit -m "feat: add CAD adapter import models"
```

---

### Task 2: Parse Basic DXF Rooms and Text

**Files:**
- Create: `src/cad_budget/dxf_adapter.py`
- Test: `tests/test_dxf_adapter.py`

- [ ] **Step 1: Write failing DXF room/text tests**

Create `tests/test_dxf_adapter.py`:

```python
from pathlib import Path

import ezdxf

from cad_budget.cad_adapter_models import CadImportOptions, CadUnit
from cad_budget.dxf_adapter import import_dxf


def _save_doc(path: Path, doc: ezdxf.EzDxf) -> Path:
    doc.saveas(path)
    return path


def test_import_dxf_reads_closed_room_and_text(tmp_path: Path):
    doc = ezdxf.new("R2010")
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
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_closed_room_and_text -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cad_budget.dxf_adapter'`.

- [ ] **Step 3: Implement minimal DXF import for rooms and text**

Create `src/cad_budget/dxf_adapter.py`:

```python
from collections.abc import Iterable
from math import ceil, cos, pi, sin

import ezdxf
from ezdxf.math import Vec2, bulge_to_arc
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.cad_adapter_models import (
    AdapterIssue,
    AdapterSeverity,
    CadImportOptions,
    CadImportResult,
    CadUnit,
)
from cad_budget.models import LayerName, Point, ProjectInput, RoomBoundary, TextMarker


_UNIT_SCALE_TO_METERS = {
    CadUnit.MILLIMETER: 0.001,
    CadUnit.CENTIMETER: 0.01,
    CadUnit.METER: 1.0,
}

_DXF_INSUNITS = {
    4: CadUnit.MILLIMETER,
    5: CadUnit.CENTIMETER,
    6: CadUnit.METER,
}


def _scale(value: float, unit: CadUnit) -> float:
    return value * _UNIT_SCALE_TO_METERS[unit]


def _entity_id(entity) -> str:
    return str(entity.dxf.handle)


def _layer(entity) -> str:
    return str(entity.dxf.layer).upper()


def _point(x: float, y: float, unit: CadUnit) -> Point:
    return Point(x=_scale(float(x), unit), y=_scale(float(y), unit))


def _arc_points_from_bulge(start: tuple[float, float], end: tuple[float, float], bulge: float, unit: CadUnit) -> list[Point]:
    center, start_angle, end_angle, radius = bulge_to_arc(Vec2(start), Vec2(end), bulge)
    angle_span = end_angle - start_angle
    if bulge < 0 and angle_span > 0:
        angle_span -= 2 * pi
    if bulge > 0 and angle_span < 0:
        angle_span += 2 * pi
    segment_count = max(4, ceil(abs(angle_span) / (pi / 12)))
    points: list[Point] = []
    for index in range(1, segment_count + 1):
        angle = start_angle + angle_span * index / segment_count
        x = center.x + radius * cos(angle)
        y = center.y + radius * sin(angle)
        points.append(_point(x, y, unit))
    return points


def _lwpolyline_points(entity, unit: CadUnit) -> list[Point]:
    raw_vertices = list(entity.get_points("xyb"))
    if not raw_vertices:
        return []
    points = [_point(raw_vertices[0][0], raw_vertices[0][1], unit)]
    for current, following in zip(raw_vertices, raw_vertices[1:]):
        start = (current[0], current[1])
        end = (following[0], following[1])
        bulge = float(current[2] or 0)
        if bulge:
            points.extend(_arc_points_from_bulge(start, end, bulge, unit))
        else:
            points.append(_point(end[0], end[1], unit))
    if points and (points[0].x != points[-1].x or points[0].y != points[-1].y):
        points.append(points[0])
    return points


def _file_unit_issue(doc, options: CadImportOptions) -> AdapterIssue | None:
    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    file_unit = _DXF_INSUNITS.get(insunits)
    if file_unit is None:
        return AdapterIssue(
            code="CAD_UNIT_UNCONFIRMED",
            message="DXF unit is missing or unsupported; using user-confirmed unit.",
        )
    if file_unit != options.confirmed_unit:
        return AdapterIssue(
            code="CAD_UNIT_CONFLICT",
            message=f"DXF unit is {file_unit.value}, but user confirmed {options.confirmed_unit.value}.",
            severity=AdapterSeverity.BLOCKER,
        )
    return None


def _text_point(entity, unit: CadUnit) -> Point:
    insert = entity.dxf.insert
    return _point(insert.x, insert.y, unit)


def _text_value(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return str(entity.dxf.text).strip()


def _polygon_from_room(room: RoomBoundary) -> Polygon:
    return Polygon([(point.x, point.y) for point in room.points])


def _assign_text_names(rooms: list[RoomBoundary], texts: list[TextMarker]) -> None:
    for room in rooms:
        polygon = _polygon_from_room(room)
        matches = [text for text in texts if polygon.contains(ShapelyPoint(text.point.x, text.point.y))]
        if len(matches) == 1:
            room.name = matches[0].text


def _iter_modelspace(doc) -> Iterable:
    return doc.modelspace()


def import_dxf(options: CadImportOptions) -> CadImportResult:
    issues: list[AdapterIssue] = []
    try:
        doc = ezdxf.readfile(options.source_path)
    except (OSError, ezdxf.DXFError) as exc:
        return CadImportResult(
            source_path=options.source_path,
            dxf_path=options.source_path,
            issues=[
                AdapterIssue(
                    code="DXF_READ_FAILED",
                    message=f"Failed to read DXF: {exc}",
                    severity=AdapterSeverity.BLOCKER,
                )
            ],
        )

    unit_issue = _file_unit_issue(doc, options)
    if unit_issue is not None:
        issues.append(unit_issue)

    rooms: list[RoomBoundary] = []
    texts: list[TextMarker] = []

    for entity in _iter_modelspace(doc):
        layer = _layer(entity)
        if layer == LayerName.QUOTE_ROOM.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            try:
                rooms.append(RoomBoundary(id=_entity_id(entity), points=points))
            except ValueError as exc:
                issues.append(
                    AdapterIssue(
                        code="ROOM_BOUNDARY_INVALID",
                        message=str(exc),
                        severity=AdapterSeverity.BLOCKER,
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
        elif layer == LayerName.QUOTE_TEXT.value and entity.dxftype() in {"TEXT", "MTEXT"}:
            value = _text_value(entity)
            if value:
                texts.append(TextMarker(id=_entity_id(entity), text=value, point=_text_point(entity, options.confirmed_unit)))

    if not rooms:
        issues.append(
            AdapterIssue(
                code="QUOTE_ROOM_MISSING",
                message="DXF does not contain any closed room boundary on QUOTE_ROOM.",
                severity=AdapterSeverity.BLOCKER,
                layer=LayerName.QUOTE_ROOM.value,
            )
        )

    _assign_text_names(rooms, texts)
    project = ProjectInput(
        project_name=options.project_name,
        default_height=options.default_height,
        default_window_height=options.default_window_height,
        floor_heights=options.floor_heights,
        rooms=rooms,
        texts=texts,
    )
    return CadImportResult(project=project, issues=issues, source_path=options.source_path, dxf_path=options.source_path)
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_closed_room_and_text -q
```

Expected: PASS.

- [ ] **Step 5: Add tests for missing rooms and invalid DXF**

Append to `tests/test_dxf_adapter.py`:

```python
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
```

- [ ] **Step 6: Run DXF adapter tests**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/cad_budget/dxf_adapter.py tests/test_dxf_adapter.py
git commit -m "feat: import DXF rooms and text"
```

---

### Task 3: Parse Windows, Doors, Walls, and Openings

**Files:**
- Modify: `src/cad_budget/dxf_adapter.py`
- Test: `tests/test_dxf_adapter.py`

- [ ] **Step 1: Write failing tests for window closed outlines and wall/opening layers**

Append to `tests/test_dxf_adapter.py`:

```python
def test_import_dxf_reads_window_outline_door_wall_and_opening(tmp_path: Path):
    doc = ezdxf.new("R2010")
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
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_window_outline_door_wall_and_opening -q
```

Expected: FAIL because windows, doors, walls, and openings are not parsed yet.

- [ ] **Step 3: Implement generic polyline extraction and outline width inference**

Modify `src/cad_budget/dxf_adapter.py` by adding these imports:

```python
from math import dist

from cad_budget.models import DoorMarker, PolylineMarker, WindowMarker
```

Add helpers:

```python
def _polyline_length(points: list[Point]) -> float:
    return sum(
        dist((start.x, start.y), (end.x, end.y))
        for start, end in zip(points, points[1:])
    )


def _outline_centroid(points: list[Point]) -> Point:
    unique = points[:-1] if len(points) > 1 and points[0] == points[-1] else points
    x = sum(point.x for point in unique) / len(unique)
    y = sum(point.y for point in unique) / len(unique)
    return Point(x=x, y=y)


def _outline_width(points: list[Point]) -> float:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    width_x = max(xs) - min(xs)
    width_y = max(ys) - min(ys)
    return max(width_x, width_y)


def _line_midpoint(points: list[Point]) -> Point:
    first = points[0]
    last = points[-1]
    return Point(x=(first.x + last.x) / 2, y=(first.y + last.y) / 2)
```

Inside `import_dxf`, initialize:

```python
windows: list[WindowMarker] = []
doors: list[DoorMarker] = []
walls: list[PolylineMarker] = []
openings: list[PolylineMarker] = []
```

Extend the entity loop:

```python
        elif layer == LayerName.QUOTE_WINDOW.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 4 and points[0] == points[-1]:
                windows.append(
                    WindowMarker(
                        id=_entity_id(entity),
                        point=_outline_centroid(points),
                        width=_outline_width(points),
                        height=None,
                        attributes={"source": "closed_outline"},
                    )
                )
            else:
                issues.append(
                    AdapterIssue(
                        code="WINDOW_OUTLINE_NOT_CLOSED",
                        message="QUOTE_WINDOW entity is not a closed outline.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
        elif layer == LayerName.QUOTE_DOOR.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            doors.append(
                DoorMarker(
                    id=_entity_id(entity),
                    point=_line_midpoint(points),
                    width=_polyline_length(points),
                    attributes={"source": "geometry"},
                )
            )
        elif layer == LayerName.QUOTE_WALL.value and entity.dxftype() == "LWPOLYLINE":
            walls.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_WALL, points=_lwpolyline_points(entity, options.confirmed_unit)))
        elif layer == LayerName.QUOTE_OPENING.value and entity.dxftype() == "LWPOLYLINE":
            openings.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_OPENING, points=_lwpolyline_points(entity, options.confirmed_unit)))
```

Pass the new collections into `ProjectInput`:

```python
        windows=windows,
        doors=doors,
        walls=walls,
        openings=openings,
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_window_outline_door_wall_and_opening -q
```

Expected: PASS.

- [ ] **Step 5: Add a test for polygon window width**

Append to `tests/test_dxf_adapter.py`:

```python
def test_import_dxf_infers_polygon_window_width_from_extents(tmp_path: Path):
    doc = ezdxf.new("R2010")
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
```

- [ ] **Step 6: Run DXF adapter tests**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/cad_budget/dxf_adapter.py tests/test_dxf_adapter.py
git commit -m "feat: import CAD openings and wall geometry"
```

---

### Task 4: Support Floor, Height, Void, and Exterior Layers

**Files:**
- Modify: `src/cad_budget/dxf_adapter.py`
- Test: `tests/test_dxf_adapter.py`

- [ ] **Step 1: Write failing tests for height, void, and exterior layers**

Append to `tests/test_dxf_adapter.py`:

```python
def test_import_dxf_reads_height_void_and_exterior_layers(tmp_path: Path):
    doc = ezdxf.new("R2010")
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
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_height_void_and_exterior_layers -q
```

Expected: FAIL because these layers are not parsed yet.

- [ ] **Step 3: Implement special layer parsing**

Modify imports in `src/cad_budget/dxf_adapter.py`:

```python
from cad_budget.models import DoorMarker, HeightMarker, PolylineMarker, VoidMarker, WindowMarker
```

Initialize collections inside `import_dxf`:

```python
heights: list[HeightMarker] = []
voids: list[VoidMarker] = []
exterior_walls: list[PolylineMarker] = []
exterior_openings: list[PolylineMarker] = []
```

Add helper:

```python
def _parse_float_text(value: str) -> float | None:
    try:
        return float(value.strip().replace("m", "").replace("M", ""))
    except ValueError:
        return None
```

Extend the entity loop:

```python
        elif layer == LayerName.QUOTE_HEIGHT.value and entity.dxftype() in {"TEXT", "MTEXT"}:
            height = _parse_float_text(_text_value(entity))
            if height is None:
                issues.append(
                    AdapterIssue(
                        code="HEIGHT_TEXT_INVALID",
                        message="QUOTE_HEIGHT text cannot be parsed as a number.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
            else:
                heights.append(HeightMarker(id=_entity_id(entity), point=_text_point(entity, options.confirmed_unit), height=height))
        elif layer == LayerName.QUOTE_VOID.value and entity.dxftype() == "LWPOLYLINE":
            voids.append(VoidMarker(id=_entity_id(entity), points=_lwpolyline_points(entity, options.confirmed_unit)))
        elif layer == LayerName.QUOTE_EXT_WALL.value and entity.dxftype() == "LWPOLYLINE":
            exterior_walls.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_EXT_WALL, points=_lwpolyline_points(entity, options.confirmed_unit)))
        elif layer == LayerName.QUOTE_EXT_OPENING.value and entity.dxftype() == "LWPOLYLINE":
            exterior_openings.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_EXT_OPENING, points=_lwpolyline_points(entity, options.confirmed_unit)))
```

Pass collections into `ProjectInput`:

```python
        heights=heights,
        voids=voids,
        exterior_walls=exterior_walls,
        exterior_openings=exterior_openings,
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python -m pytest tests/test_dxf_adapter.py::test_import_dxf_reads_height_void_and_exterior_layers -q
```

Expected: PASS.

- [ ] **Step 5: Run all adapter tests**

Run:

```bash
python -m pytest tests/test_cad_adapter_models.py tests/test_dxf_adapter.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/cad_budget/dxf_adapter.py tests/test_dxf_adapter.py
git commit -m "feat: import CAD height and special layers"
```

---

### Task 5: Add DWG Conversion Wrapper

**Files:**
- Create: `src/cad_budget/dwg_converter.py`
- Test: `tests/test_dwg_converter.py`

- [ ] **Step 1: Write failing converter tests**

Create `tests/test_dwg_converter.py`:

```python
from pathlib import Path

from cad_budget.dwg_converter import convert_dwg_to_dxf


def test_convert_dwg_to_dxf_requires_converter_command(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(dwg_path, tmp_path, converter_command=None)

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERTER_NOT_CONFIGURED"


def test_convert_dwg_to_dxf_reports_failed_command(tmp_path: Path):
    dwg_path = tmp_path / "plan.dwg"
    dwg_path.write_bytes(b"fake")

    result = convert_dwg_to_dxf(
        dwg_path,
        tmp_path,
        converter_command=["python", "-c", "import sys; sys.exit(7)"],
    )

    assert result.dxf_path is None
    assert result.issue is not None
    assert result.issue.code == "DWG_CONVERSION_FAILED"
```

- [ ] **Step 2: Run converter tests and verify they fail**

Run:

```bash
python -m pytest tests/test_dwg_converter.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement converter wrapper**

Create `src/cad_budget/dwg_converter.py`:

```python
from pathlib import Path
import subprocess

from pydantic import BaseModel

from cad_budget.cad_adapter_models import AdapterIssue, AdapterSeverity


class DwgConversionResult(BaseModel):
    dxf_path: Path | None = None
    issue: AdapterIssue | None = None


def convert_dwg_to_dxf(
    dwg_path: Path,
    output_dir: Path,
    converter_command: list[str] | None,
) -> DwgConversionResult:
    if converter_command is None:
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERTER_NOT_CONFIGURED",
                message="DWG input requires a configured DWG-to-DXF converter.",
                severity=AdapterSeverity.BLOCKER,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = output_dir / f"{dwg_path.stem}.dxf"
    command = [part.replace("{input}", str(dwg_path)).replace("{output}", str(dxf_path)) for part in converter_command]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERSION_FAILED",
                message=f"DWG conversion failed with exit code {completed.returncode}: {completed.stderr.strip()}",
                severity=AdapterSeverity.BLOCKER,
            )
        )

    if not dxf_path.exists():
        return DwgConversionResult(
            issue=AdapterIssue(
                code="DWG_CONVERSION_OUTPUT_MISSING",
                message=f"DWG converter succeeded but did not create {dxf_path}.",
                severity=AdapterSeverity.BLOCKER,
            )
        )

    return DwgConversionResult(dxf_path=dxf_path)
```

- [ ] **Step 4: Run converter tests**

Run:

```bash
python -m pytest tests/test_dwg_converter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad_budget/dwg_converter.py tests/test_dwg_converter.py
git commit -m "feat: add DWG conversion wrapper"
```

---

### Task 6: Add CLI Import Command

**Files:**
- Modify: `src/cad_budget/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
import ezdxf


def test_cli_import_cad_dxf_writes_project_json(tmp_path: Path):
    doc = ezdxf.new("R2010")
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
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_import_cad_dxf_writes_project_json tests/test_cli.py::test_cli_import_cad_dwg_requires_converter -q
```

Expected: FAIL because `import-cad` does not exist.

- [ ] **Step 3: Implement `import-cad` command**

Modify `src/cad_budget/cli.py` imports:

```python
from cad_budget.cad_adapter_models import CadImportOptions, CadUnit
from cad_budget.dwg_converter import convert_dwg_to_dxf
from cad_budget.dxf_adapter import import_dxf
```

Add this command below `calculate`:

```python
@app.command("import-cad")
def import_cad(
    input_cad: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for generated ProjectInput JSON."),
    unit: CadUnit = typer.Option(CadUnit.MILLIMETER, "--unit", help="Confirmed project CAD unit."),
    project_name: str | None = typer.Option(None, "--project-name", help="Optional project name override."),
    dwg_converter: list[str] | None = typer.Option(None, "--dwg-converter", help="DWG converter command parts; use {input} and {output} placeholders."),
) -> None:
    suffix = input_cad.suffix.lower()
    if suffix == ".dxf":
        result = import_dxf(
            CadImportOptions(
                source_path=input_cad,
                confirmed_unit=unit,
                project_name_override=project_name,
            )
        )
    elif suffix == ".dwg":
        conversion = convert_dwg_to_dxf(input_cad, json_output.parent / "_converted", dwg_converter)
        if conversion.issue is not None:
            typer.echo(conversion.issue.message, err=True)
            raise typer.Exit(code=1)
        result = import_dxf(
            CadImportOptions(
                source_path=conversion.dxf_path,
                confirmed_unit=unit,
                project_name_override=project_name or input_cad.stem,
            )
        )
    else:
        typer.echo("Unsupported CAD file type. Use .dxf or .dwg.", err=True)
        raise typer.Exit(code=1)

    for issue in result.issues:
        typer.echo(f"{issue.severity.value}: {issue.code}: {issue.message}", err=True)

    if result.has_blockers or result.project is None:
        raise typer.Exit(code=1)

    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(result.project.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Failed to write ProjectInput JSON '{json_output}': {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {json_output}")
```

- [ ] **Step 4: Run the focused CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_import_cad_dxf_writes_project_json tests/test_cli.py::test_cli_import_cad_dwg_requires_converter -q
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/cad_budget/cli.py tests/test_cli.py
git commit -m "feat: add CAD import CLI"
```

---

### Task 7: Document the CAD Import Workflow

**Files:**
- Modify: `README.md`
- Test: manual command verification

- [ ] **Step 1: Add README usage section**

Append this section to `README.md`:

```markdown
## CAD Import Workflow

The first CAD import path is:

```text
DXF / DWG -> CAD Adapter -> ProjectInput JSON -> Quantity calculation -> JSON / Excel result
```

DXF can be imported directly:

```bash
cad-budget import-cad plan.dxf --json-output project.json --unit mm
cad-budget calculate project.json --json-output result.json --excel-output result.xlsx
```

DWG requires a configured converter command. The command may use `{input}` and `{output}` placeholders:

```bash
cad-budget import-cad plan.dwg --json-output project.json --unit mm --dwg-converter "converter" --dwg-converter "{input}" --dwg-converter "{output}"
```

If DWG conversion fails, ask the designer to save the drawing as DXF from CAD and upload the DXF.

Supported first-version layers:

```text
QUOTE_ROOM
QUOTE_TEXT
QUOTE_WINDOW
QUOTE_DOOR
QUOTE_WALL
QUOTE_OPENING
QUOTE_HEIGHT
QUOTE_VOID
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

Window recognition supports block attributes when available. Without attributes, the adapter reads a closed window opening outline on `QUOTE_WINDOW`; the outline may be rectangular, polygonal, or an arc-based closed shape. Window height still comes from attributes/tags when available, otherwise the default window height is used later by the quantity engine and marked as inferred.
```

- [ ] **Step 2: Verify the README command path manually**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document CAD import workflow"
```

---

### Task 8: Final Verification and Review

**Files:**
- All modified files

- [ ] **Step 1: Run formatting-safe diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 2: Run full tests**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Smoke test full pipeline with generated DXF**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_import_cad_dxf_writes_project_json -q
```

Expected: PASS and generated ProjectInput includes at least one `QUOTE_ROOM` room.

- [ ] **Step 4: Review final diff**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: working tree is clean after the task commits, and recent commits include the CAD adapter implementation commits.

---

## Self-Review

Spec coverage:

- DXF direct parsing: Tasks 2, 3, 4, and 6.
- DWG automatic conversion with fallback: Tasks 5 and 6.
- Adapter boundary `CAD -> ProjectInput -> quantity engine`: Tasks 1, 2, and 6.
- Unit confirmation: Tasks 1, 2, and 6 use `CadImportOptions.confirmed_unit` and compare supported DXF `$INSUNITS` values against it.
- Existing door model support: Task 3 handles geometric fallback from `QUOTE_DOOR`; block attribute extraction will use the same output fields when real door blocks are provided.
- Window closed outlines including rectangles, polygons, and bulge arc-based outlines: Tasks 2 and 3 flatten LWPOLYLINE bulges and infer width from the resulting closed outline.
- Severe/minor issues: Tasks 1 and 2 introduce issue severity; Task 6 blocks on blockers and prints warnings.
- Special layers: Task 4.
- Editable table and final quantity calculation: existing `calculate` command remains unchanged and consumes generated `ProjectInput`.

Known first-pass limitations to keep explicit:

- DWG conversion depends on an external configured converter.
- DXF unit double-validation supports common `$INSUNITS` values for millimeter, centimeter, and meter. Unsupported or missing units generate a warning and still use the user-confirmed unit.
- Arc-based window outlines are flattened from LWPOLYLINE bulge values; real project files should still be sampled during implementation review to tune segment density and wall matching tolerance.
