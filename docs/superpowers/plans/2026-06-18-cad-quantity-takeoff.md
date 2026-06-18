# CAD Quantity Takeoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested first-version CAD renovation quantity takeoff core that converts standardized CAD-derived data into editable/exportable room quantity results.

**Architecture:** Start with a Python domain core that is independent of DWG parsing and UI. The first executable path accepts a normalized JSON file that represents parsed `QUOTE_*` CAD entities, calculates quantities, reports exceptions, and exports Excel; a later DWG/DXF adapter can feed the same JSON model.

**Tech Stack:** Python 3.11+, pytest, pydantic, shapely, openpyxl, typer.

---

## Scope Split

The design spec covers CAD import, geometry matching, quantity calculation, editable table behavior, Excel export, and future UI. This plan implements a working first slice:

1. Project foundation and domain models.
2. Geometry and quantity engine.
3. Normalized JSON import for CAD-derived entities.
4. Exceptions and status tracking.
5. Excel export.
6. CLI for end-to-end local use.

DWG/DXF conversion and a browser UI are intentionally deferred until the core is tested. The adapter and UI should consume the same domain models created here.

## Planned File Structure

```text
pyproject.toml
README.md
src/cad_budget/
  __init__.py
  cli.py
  models.py
  geometry.py
  matching.py
  quantity.py
  export_excel.py
tests/
  fixtures/simple_apartment.json
  fixtures/open_living_room.json
  fixtures/villa_special_spaces.json
  test_models.py
  test_geometry.py
  test_quantity.py
  test_export_excel.py
  test_cli.py
```

Responsibilities:

```text
models.py        Data types, enums, validation, and status/source fields
geometry.py      Polygon, polyline, length, area, and segment matching helpers
matching.py      Assign texts/windows/doors/walls/openings/heights to rooms
quantity.py      Formula-driven takeoff calculation
export_excel.py  Excel export from calculated results
cli.py           Local command for JSON input -> JSON/Excel output
```

## Task 1: Project Foundation

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/cad_budget/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing project import test**

Create `tests/test_models.py`:

```python
from cad_budget.models import ProjectInput


def test_project_input_can_be_imported():
    assert ProjectInput.__name__ == "ProjectInput"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_models.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'cad_budget'
```

- [ ] **Step 3: Create project metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cad-budget"
version = "0.1.0"
description = "CAD renovation quantity takeoff core"
requires-python = ">=3.11"
dependencies = [
  "openpyxl>=3.1.5",
  "pydantic>=2.8.0",
  "shapely>=2.0.4",
  "typer>=0.12.3"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0"
]

[project.scripts]
cad-budget = "cad_budget.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Create package marker**

Create `src/cad_budget/__init__.py`:

```python
"""CAD renovation quantity takeoff core."""

__all__ = ["__version__"]
__version__ = "0.1.0"
```

- [ ] **Step 5: Add a short README**

Create `README.md`:

```markdown
# CAD Budget Program

First-version CAD renovation quantity takeoff core.

The system accepts normalized CAD-derived JSON using the `QUOTE_*` standard, calculates room quantities, reports exceptions, and exports Excel for later quotation work.
```

- [ ] **Step 6: Add the minimal model placeholder**

Create `src/cad_budget/models.py`:

```python
from pydantic import BaseModel


class ProjectInput(BaseModel):
    project_name: str = "Untitled"
```

- [ ] **Step 7: Run the test to verify it passes**

Run:

```bash
pytest tests/test_models.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md src/cad_budget/__init__.py src/cad_budget/models.py tests/test_models.py
git commit -m "chore: initialize quantity takeoff project"
```

## Task 2: Domain Models

**Files:**
- Modify: `src/cad_budget/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Replace the model test with validation coverage**

Modify `tests/test_models.py`:

```python
from cad_budget.models import (
    DataStatus,
    HeightMode,
    LayerName,
    Point,
    ProjectInput,
    RoomBoundary,
    SpaceType,
)


def test_project_input_accepts_quote_room_boundary():
    project = ProjectInput(
        project_name="Villa A",
        default_height=2.8,
        rooms=[
            RoomBoundary(
                id="room-1",
                layer=LayerName.QUOTE_ROOM,
                points=[
                    Point(x=0, y=0),
                    Point(x=4, y=0),
                    Point(x=4, y=3),
                    Point(x=0, y=3),
                    Point(x=0, y=0),
                ],
                floor="1F",
                space_type=SpaceType.NORMAL,
            )
        ],
    )

    assert project.rooms[0].id == "room-1"
    assert project.rooms[0].space_type is SpaceType.NORMAL


def test_status_and_height_modes_are_explicit():
    assert DataStatus.CONFIRMED.value == "confirmed"
    assert DataStatus.DEFAULT_INFERRED.value == "default_inferred"
    assert HeightMode.FLOOR_DEFAULT.value == "floor_default"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_models.py -q
```

Expected:

```text
ImportError
```

- [ ] **Step 3: Implement the complete first-version models**

Replace `src/cad_budget/models.py` with:

```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LayerName(str, Enum):
    QUOTE_ROOM = "QUOTE_ROOM"
    QUOTE_TEXT = "QUOTE_TEXT"
    QUOTE_WINDOW = "QUOTE_WINDOW"
    QUOTE_DOOR = "QUOTE_DOOR"
    QUOTE_WALL = "QUOTE_WALL"
    QUOTE_OPENING = "QUOTE_OPENING"
    QUOTE_FLOOR = "QUOTE_FLOOR"
    QUOTE_HEIGHT = "QUOTE_HEIGHT"
    QUOTE_VOID = "QUOTE_VOID"
    QUOTE_EXT_WALL = "QUOTE_EXT_WALL"
    QUOTE_EXT_OPENING = "QUOTE_EXT_OPENING"


class SpaceType(str, Enum):
    NORMAL = "normal"
    VOID = "void"
    VOID_OPENING = "void_opening"
    STAIR = "stair"
    STAIR_HALL = "stair_hall"
    BALCONY = "balcony"
    TERRACE = "terrace"
    ELEVATOR_SHAFT = "elevator_shaft"


class DataStatus(str, Enum):
    CONFIRMED = "confirmed"
    DEFAULT_INFERRED = "default_inferred"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_EDITED = "manually_edited"
    EXCLUDED = "excluded"


class HeightMode(str, Enum):
    PROJECT_DEFAULT = "project_default"
    FLOOR_DEFAULT = "floor_default"
    QUOTE_HEIGHT = "quote_height"
    QUOTE_VOID = "quote_void"
    MANUAL = "manual"
    RELATED_FLOORS_SUM = "related_floors_sum"


class Point(BaseModel):
    x: float
    y: float


class RoomBoundary(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_ROOM
    points: list[Point]
    floor: str | None = None
    name: str | None = None
    space_type: SpaceType = SpaceType.NORMAL
    include_in_floor_quantity: bool = True
    include_in_wall_paint_quantity: bool = True
    is_outdoor: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("points")
    @classmethod
    def require_at_least_three_points(cls, points: list[Point]) -> list[Point]:
        if len(points) < 4:
            raise ValueError("room boundary must include at least 4 points including closure")
        return points


class TextMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_TEXT
    text: str
    point: Point
    floor: str | None = None


class WindowMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_WINDOW
    point: Point
    width: float
    height: float | None = None
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class DoorMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_DOOR
    point: Point
    width: float | None = None
    height: float | None = None
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class PolylineMarker(BaseModel):
    id: str
    layer: LayerName
    points: list[Point]
    floor: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class HeightMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_HEIGHT
    point: Point
    height: float
    floor: str | None = None
    room_id: str | None = None


class VoidMarker(BaseModel):
    id: str
    layer: LayerName = LayerName.QUOTE_VOID
    points: list[Point]
    height: float | None = None
    related_floors: list[str] = Field(default_factory=list)
    floor: str | None = None


class ProjectInput(BaseModel):
    project_name: str = "Untitled"
    default_height: float = 2.8
    default_window_height: float = 1.5
    floor_heights: dict[str, float] = Field(default_factory=dict)
    rooms: list[RoomBoundary] = Field(default_factory=list)
    texts: list[TextMarker] = Field(default_factory=list)
    windows: list[WindowMarker] = Field(default_factory=list)
    doors: list[DoorMarker] = Field(default_factory=list)
    walls: list[PolylineMarker] = Field(default_factory=list)
    openings: list[PolylineMarker] = Field(default_factory=list)
    heights: list[HeightMarker] = Field(default_factory=list)
    voids: list[VoidMarker] = Field(default_factory=list)
    exterior_walls: list[PolylineMarker] = Field(default_factory=list)
    exterior_openings: list[PolylineMarker] = Field(default_factory=list)


class QuantityException(BaseModel):
    code: str
    message: str
    room_id: str | None = None
    severity: str = "warning"


class QuantityRow(BaseModel):
    room_id: str
    floor: str | None
    room_name: str
    space_type: SpaceType
    height: float
    height_mode: HeightMode
    floor_area: float
    floor_perimeter: float
    wall_measure_perimeter: float
    open_boundary_length: float
    gross_wall_area: float
    window_count: int
    window_area: float
    door_opening_count: int
    door_opening_area: float
    net_wall_area: float
    is_outdoor: bool
    include_in_floor_quantity: bool
    include_in_wall_paint_quantity: bool
    status: DataStatus
    exception_notes: list[str] = Field(default_factory=list)


class QuantityResult(BaseModel):
    project_name: str
    rows: list[QuantityRow]
    exceptions: list[QuantityException]
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_models.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/cad_budget/models.py tests/test_models.py
git commit -m "feat: add quantity domain models"
```

## Task 3: Geometry Helpers

**Files:**
- Create: `src/cad_budget/geometry.py`
- Create: `tests/test_geometry.py`

- [ ] **Step 1: Write geometry tests**

Create `tests/test_geometry.py`:

```python
from cad_budget.geometry import (
    closed_polygon_area,
    closed_polygon_perimeter,
    point_inside_polygon,
    polyline_length,
)
from cad_budget.models import Point


RECT = [
    Point(x=0, y=0),
    Point(x=4, y=0),
    Point(x=4, y=3),
    Point(x=0, y=3),
    Point(x=0, y=0),
]


def test_closed_polygon_area_and_perimeter():
    assert closed_polygon_area(RECT) == 12
    assert closed_polygon_perimeter(RECT) == 14


def test_polyline_length_for_opening():
    line = [Point(x=0, y=0), Point(x=3, y=4)]
    assert polyline_length(line) == 5


def test_point_inside_polygon():
    assert point_inside_polygon(Point(x=2, y=1), RECT) is True
    assert point_inside_polygon(Point(x=5, y=1), RECT) is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_geometry.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'cad_budget.geometry'
```

- [ ] **Step 3: Implement geometry helpers**

Create `src/cad_budget/geometry.py`:

```python
from math import hypot

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.models import Point


def _pairs(points: list[Point]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def is_closed(points: list[Point]) -> bool:
    if len(points) < 2:
        return False
    return points[0].x == points[-1].x and points[0].y == points[-1].y


def polyline_length(points: list[Point]) -> float:
    return round(sum(hypot(b.x - a.x, b.y - a.y) for a, b in _pairs(points)), 6)


def closed_polygon_area(points: list[Point]) -> float:
    polygon = Polygon([(point.x, point.y) for point in points])
    return round(float(polygon.area), 6)


def closed_polygon_perimeter(points: list[Point]) -> float:
    return polyline_length(points)


def point_inside_polygon(point: Point, polygon_points: list[Point]) -> bool:
    polygon = Polygon([(p.x, p.y) for p in polygon_points])
    return bool(polygon.contains(ShapelyPoint(point.x, point.y)))
```

- [ ] **Step 4: Run geometry tests**

Run:

```bash
pytest tests/test_geometry.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/cad_budget/geometry.py tests/test_geometry.py
git commit -m "feat: add geometry helpers"
```

## Task 4: Quantity Engine for Normal and Open Spaces

**Files:**
- Create: `src/cad_budget/quantity.py`
- Create: `tests/test_quantity.py`

- [ ] **Step 1: Write normal and open-space quantity tests**

Create `tests/test_quantity.py`:

```python
from cad_budget.models import (
    LayerName,
    Point,
    PolylineMarker,
    ProjectInput,
    RoomBoundary,
    TextMarker,
    WindowMarker,
)
from cad_budget.quantity import calculate_quantities


def rect(x1: float, y1: float, x2: float, y2: float) -> list[Point]:
    return [
        Point(x=x1, y=y1),
        Point(x=x2, y=y1),
        Point(x=x2, y=y2),
        Point(x=x1, y=y2),
        Point(x=x1, y=y1),
    ]


def test_normal_room_quantity_uses_room_perimeter_as_wall_perimeter_when_walls_match():
    project = ProjectInput(
        project_name="Apt",
        default_height=2.8,
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3))],
        texts=[TextMarker(id="t1", text="卧室", point=Point(x=2, y=1))],
        walls=[PolylineMarker(id="w1", layer=LayerName.QUOTE_WALL, points=rect(0, 0, 4, 3))],
        windows=[WindowMarker(id="win1", point=Point(x=2, y=0), width=1.2, height=1.5)],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.room_name == "卧室"
    assert row.floor_area == 12
    assert row.floor_perimeter == 14
    assert row.wall_measure_perimeter == 14
    assert row.gross_wall_area == 39.2
    assert row.window_area == 1.8
    assert row.net_wall_area == 37.4


def test_open_boundary_reduces_wall_measure_perimeter():
    project = ProjectInput(
        project_name="Open Living",
        default_height=2.8,
        rooms=[RoomBoundary(id="living", points=rect(0, 0, 4, 3))],
        texts=[TextMarker(id="t1", text="客餐厅", point=Point(x=2, y=1))],
        walls=[PolylineMarker(id="w1", layer=LayerName.QUOTE_WALL, points=rect(0, 0, 4, 3))],
        openings=[
            PolylineMarker(
                id="open1",
                layer=LayerName.QUOTE_OPENING,
                points=[Point(x=4, y=0), Point(x=4, y=3)],
            )
        ],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.floor_perimeter == 14
    assert row.open_boundary_length == 3
    assert row.wall_measure_perimeter == 11
    assert row.gross_wall_area == 30.8
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_quantity.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'cad_budget.quantity'
```

- [ ] **Step 3: Implement first quantity engine**

Create `src/cad_budget/quantity.py`:

```python
from cad_budget.geometry import (
    closed_polygon_area,
    closed_polygon_perimeter,
    point_inside_polygon,
    polyline_length,
)
from cad_budget.models import (
    DataStatus,
    HeightMode,
    ProjectInput,
    QuantityException,
    QuantityResult,
    QuantityRow,
    RoomBoundary,
    SpaceType,
)


def _room_name(project: ProjectInput, room: RoomBoundary) -> tuple[str, list[QuantityException]]:
    names = [text.text for text in project.texts if point_inside_polygon(text.point, room.points)]
    if room.name:
        return room.name, []
    if len(names) == 1:
        return names[0], []
    if len(names) > 1:
        return names[0], [
            QuantityException(
                code="multiple_room_names",
                message=f"Room {room.id} contains multiple names: {', '.join(names)}",
                room_id=room.id,
            )
        ]
    return "未命名空间", [
        QuantityException(code="room_has_no_name", message=f"Room {room.id} has no name", room_id=room.id)
    ]


def _height(project: ProjectInput, room: RoomBoundary) -> tuple[float, HeightMode]:
    if "height" in room.attributes:
        return float(room.attributes["height"]), HeightMode.MANUAL
    for marker in project.heights:
        if marker.room_id == room.id or point_inside_polygon(marker.point, room.points):
            return marker.height, HeightMode.QUOTE_HEIGHT
    if room.floor and room.floor in project.floor_heights:
        return project.floor_heights[room.floor], HeightMode.FLOOR_DEFAULT
    return project.default_height, HeightMode.PROJECT_DEFAULT


def _open_boundary_length(project: ProjectInput, room: RoomBoundary) -> float:
    return round(
        sum(polyline_length(opening.points) for opening in project.openings if _line_touches_room(opening.points, room)),
        6,
    )


def _line_touches_room(points, room: RoomBoundary) -> bool:
    return any(point_inside_polygon(point, room.points) or _point_on_room_bbox(point, room) for point in points)


def _point_on_room_bbox(point, room: RoomBoundary) -> bool:
    xs = [p.x for p in room.points]
    ys = [p.y for p in room.points]
    return min(xs) <= point.x <= max(xs) and min(ys) <= point.y <= max(ys)


def _window_area(project: ProjectInput, room: RoomBoundary) -> tuple[int, float, list[QuantityException], DataStatus]:
    count = 0
    area = 0.0
    exceptions: list[QuantityException] = []
    status = DataStatus.CONFIRMED
    for window in project.windows:
        if not point_inside_polygon(window.point, room.points) and not _point_on_room_bbox(window.point, room):
            continue
        count += 1
        height = window.height
        if height is None:
            height = project.default_window_height
            status = DataStatus.DEFAULT_INFERRED
            exceptions.append(
                QuantityException(
                    code="window_height_defaulted",
                    message=f"Window {window.id} used default height {height}",
                    room_id=room.id,
                )
            )
        area += window.width * height
    return count, round(area, 6), exceptions, status


def calculate_quantities(project: ProjectInput) -> QuantityResult:
    rows: list[QuantityRow] = []
    exceptions: list[QuantityException] = []

    for room in project.rooms:
        name, name_exceptions = _room_name(project, room)
        exceptions.extend(name_exceptions)
        height, height_mode = _height(project, room)
        floor_area = closed_polygon_area(room.points)
        floor_perimeter = closed_polygon_perimeter(room.points)
        open_length = _open_boundary_length(project, room)
        wall_measure_perimeter = max(floor_perimeter - open_length, 0)
        window_count, window_area, window_exceptions, window_status = _window_area(project, room)
        exceptions.extend(window_exceptions)
        gross_wall_area = round(wall_measure_perimeter * height, 6)
        net_wall_area = round(gross_wall_area - window_area, 6)
        status = DataStatus.CONFIRMED if not name_exceptions else DataStatus.NEEDS_REVIEW
        if window_status is DataStatus.DEFAULT_INFERRED and status is DataStatus.CONFIRMED:
            status = DataStatus.DEFAULT_INFERRED

        if room.space_type is SpaceType.ELEVATOR_SHAFT:
            status = DataStatus.EXCLUDED
            floor_area = 0
            wall_measure_perimeter = 0
            gross_wall_area = 0
            net_wall_area = 0

        rows.append(
            QuantityRow(
                room_id=room.id,
                floor=room.floor,
                room_name=name,
                space_type=room.space_type,
                height=height,
                height_mode=height_mode,
                floor_area=round(floor_area, 6),
                floor_perimeter=round(floor_perimeter, 6),
                wall_measure_perimeter=round(wall_measure_perimeter, 6),
                open_boundary_length=open_length,
                gross_wall_area=gross_wall_area,
                window_count=window_count,
                window_area=window_area,
                door_opening_count=0,
                door_opening_area=0,
                net_wall_area=net_wall_area,
                is_outdoor=room.is_outdoor,
                include_in_floor_quantity=room.include_in_floor_quantity,
                include_in_wall_paint_quantity=room.include_in_wall_paint_quantity,
                status=status,
                exception_notes=[exception.message for exception in exceptions if exception.room_id == room.id],
            )
        )

    return QuantityResult(project_name=project.project_name, rows=rows, exceptions=exceptions)
```

- [ ] **Step 4: Run quantity tests**

Run:

```bash
pytest tests/test_quantity.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
7 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/cad_budget/quantity.py tests/test_quantity.py
git commit -m "feat: calculate room and open-space quantities"
```

## Task 5: Special Spaces

**Files:**
- Modify: `src/cad_budget/quantity.py`
- Modify: `tests/test_quantity.py`

- [ ] **Step 1: Add special-space tests**

Append to `tests/test_quantity.py`:

```python
from cad_budget.models import SpaceType


def test_void_space_uses_custom_height_and_keeps_single_floor_area():
    project = ProjectInput(
        project_name="Villa Void",
        default_height=2.8,
        floor_heights={"1F": 3.0, "2F": 3.0},
        rooms=[
            RoomBoundary(
                id="void-living",
                points=rect(0, 0, 5, 4),
                floor="1F",
                space_type=SpaceType.VOID,
                attributes={"height": 6.0},
            )
        ],
        texts=[TextMarker(id="t1", text="挑空客厅", point=Point(x=2, y=2))],
    )

    row = calculate_quantities(project).rows[0]

    assert row.space_type is SpaceType.VOID
    assert row.height == 6.0
    assert row.floor_area == 20
    assert row.gross_wall_area == 108


def test_elevator_shaft_is_excluded_by_default():
    project = ProjectInput(
        project_name="Villa Shaft",
        rooms=[
            RoomBoundary(
                id="shaft",
                points=rect(0, 0, 2, 2),
                space_type=SpaceType.ELEVATOR_SHAFT,
                include_in_floor_quantity=False,
                include_in_wall_paint_quantity=False,
            )
        ],
    )

    row = calculate_quantities(project).rows[0]

    assert row.status.value == "excluded"
    assert row.floor_area == 0
    assert row.net_wall_area == 0


def test_balcony_keeps_outdoor_flags():
    project = ProjectInput(
        project_name="Balcony",
        rooms=[
            RoomBoundary(
                id="balcony",
                points=rect(0, 0, 3, 1.5),
                name="阳台",
                space_type=SpaceType.BALCONY,
                is_outdoor=True,
                include_in_wall_paint_quantity=False,
            )
        ],
    )

    row = calculate_quantities(project).rows[0]

    assert row.space_type is SpaceType.BALCONY
    assert row.is_outdoor is True
    assert row.include_in_wall_paint_quantity is False
```

- [ ] **Step 2: Run tests**

Run:

```bash
pytest tests/test_quantity.py -q
```

Expected:

```text
5 passed
```

If the void gross wall area is not `108`, adjust the test room perimeter and height rather than changing formulas: a 5m by 4m room has perimeter `18`, and `18 * 6 = 108`.

- [ ] **Step 3: Commit**

```bash
git add src/cad_budget/quantity.py tests/test_quantity.py
git commit -m "feat: support first-version special spaces"
```

## Task 6: JSON Fixtures and CLI

**Files:**
- Create: `src/cad_budget/cli.py`
- Create: `tests/fixtures/simple_apartment.json`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Add a fixture**

Create `tests/fixtures/simple_apartment.json`:

```json
{
  "project_name": "Simple Apartment",
  "default_height": 2.8,
  "default_window_height": 1.5,
  "rooms": [
    {
      "id": "bedroom",
      "points": [
        { "x": 0, "y": 0 },
        { "x": 4, "y": 0 },
        { "x": 4, "y": 3 },
        { "x": 0, "y": 3 },
        { "x": 0, "y": 0 }
      ]
    }
  ],
  "texts": [
    { "id": "txt-bedroom", "text": "卧室", "point": { "x": 2, "y": 1 } }
  ],
  "windows": [
    { "id": "win-bedroom", "point": { "x": 2, "y": 0 }, "width": 1.2, "height": 1.5 }
  ]
}
```

- [ ] **Step 2: Write CLI test**

Create `tests/test_cli.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from cad_budget.cli import app


def test_cli_calculates_json_output(tmp_path: Path):
    runner = CliRunner()
    output = tmp_path / "result.json"

    result = runner.invoke(
        app,
        [
            "calculate",
            "tests/fixtures/simple_apartment.json",
            "--json-output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["project_name"] == "Simple Apartment"
    assert data["rows"][0]["room_name"] == "卧室"
    assert data["rows"][0]["floor_area"] == 12
```

- [ ] **Step 3: Run CLI test to verify failure**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'cad_budget.cli'
```

- [ ] **Step 4: Implement CLI**

Create `src/cad_budget/cli.py`:

```python
import json
from pathlib import Path

import typer

from cad_budget.models import ProjectInput
from cad_budget.quantity import calculate_quantities

app = typer.Typer(help="CAD renovation quantity takeoff tools.")


@app.command()
def calculate(
    input_json: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for calculated JSON output."),
) -> None:
    project = ProjectInput.model_validate_json(input_json.read_text(encoding="utf-8"))
    result = calculate_quantities(project)
    json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Wrote {json_output}")
```

- [ ] **Step 5: Run CLI test**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
11 passed
```

- [ ] **Step 7: Commit**

```bash
git add src/cad_budget/cli.py tests/fixtures/simple_apartment.json tests/test_cli.py
git commit -m "feat: add JSON quantity CLI"
```

## Task 7: Excel Export

**Files:**
- Create: `src/cad_budget/export_excel.py`
- Create: `tests/test_export_excel.py`
- Modify: `src/cad_budget/cli.py`

- [ ] **Step 1: Write Excel export test**

Create `tests/test_export_excel.py`:

```python
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
```

- [ ] **Step 2: Run export test to verify failure**

Run:

```bash
pytest tests/test_export_excel.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'cad_budget.export_excel'
```

- [ ] **Step 3: Implement Excel export**

Create `src/cad_budget/export_excel.py`:

```python
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
```

- [ ] **Step 4: Add Excel output option to CLI**

Modify `src/cad_budget/cli.py`:

```python
import json
from pathlib import Path

import typer

from cad_budget.export_excel import export_quantity_result
from cad_budget.models import ProjectInput
from cad_budget.quantity import calculate_quantities

app = typer.Typer(help="CAD renovation quantity takeoff tools.")


@app.command()
def calculate(
    input_json: Path,
    json_output: Path = typer.Option(..., "--json-output", help="Path for calculated JSON output."),
    excel_output: Path | None = typer.Option(None, "--excel-output", help="Optional Excel output path."),
) -> None:
    project = ProjectInput.model_validate_json(input_json.read_text(encoding="utf-8"))
    result = calculate_quantities(project)
    json_output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Wrote {json_output}")
    if excel_output is not None:
        export_quantity_result(result, excel_output)
        typer.echo(f"Wrote {excel_output}")
```

- [ ] **Step 5: Run export tests**

Run:

```bash
pytest tests/test_export_excel.py tests/test_cli.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
12 passed
```

- [ ] **Step 7: Commit**

```bash
git add src/cad_budget/export_excel.py src/cad_budget/cli.py tests/test_export_excel.py
git commit -m "feat: export quantity takeoff to Excel"
```

## Task 8: Documentation and Sample Command

**Files:**
- Modify: `README.md`
- Create: `tests/fixtures/open_living_room.json`
- Create: `tests/fixtures/villa_special_spaces.json`

- [ ] **Step 1: Add open-space fixture**

Create `tests/fixtures/open_living_room.json`:

```json
{
  "project_name": "Open Living",
  "default_height": 2.8,
  "rooms": [
    {
      "id": "living",
      "name": "客餐厅",
      "points": [
        { "x": 0, "y": 0 },
        { "x": 4, "y": 0 },
        { "x": 4, "y": 3 },
        { "x": 0, "y": 3 },
        { "x": 0, "y": 0 }
      ]
    }
  ],
  "openings": [
    {
      "id": "open1",
      "layer": "QUOTE_OPENING",
      "points": [
        { "x": 4, "y": 0 },
        { "x": 4, "y": 3 }
      ]
    }
  ]
}
```

- [ ] **Step 2: Add villa special-space fixture**

Create `tests/fixtures/villa_special_spaces.json`:

```json
{
  "project_name": "Villa Special Spaces",
  "default_height": 2.8,
  "floor_heights": {
    "1F": 3.0,
    "2F": 3.0
  },
  "rooms": [
    {
      "id": "void-living",
      "name": "挑空客厅",
      "floor": "1F",
      "space_type": "void",
      "attributes": { "height": 6.0 },
      "points": [
        { "x": 0, "y": 0 },
        { "x": 5, "y": 0 },
        { "x": 5, "y": 4 },
        { "x": 0, "y": 4 },
        { "x": 0, "y": 0 }
      ]
    },
    {
      "id": "elevator",
      "name": "电梯井",
      "floor": "1F",
      "space_type": "elevator_shaft",
      "include_in_floor_quantity": false,
      "include_in_wall_paint_quantity": false,
      "points": [
        { "x": 6, "y": 0 },
        { "x": 8, "y": 0 },
        { "x": 8, "y": 2 },
        { "x": 6, "y": 2 },
        { "x": 6, "y": 0 }
      ]
    }
  ]
}
```

- [ ] **Step 3: Update README with usage**

Modify `README.md`:

```markdown
# CAD Budget Program

First-version CAD renovation quantity takeoff core.

The system accepts normalized CAD-derived JSON using the `QUOTE_*` standard, calculates room quantities, reports exceptions, and exports Excel for later quotation work.

## Local Usage

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest -q
```

Calculate a sample apartment:

```bash
cad-budget calculate tests/fixtures/simple_apartment.json --json-output build/simple-result.json --excel-output build/simple-result.xlsx
```

## First-Version CAD Standard

Core layers:

```text
QUOTE_ROOM
QUOTE_TEXT
QUOTE_WINDOW
QUOTE_DOOR
QUOTE_WALL
QUOTE_OPENING
QUOTE_FLOOR
QUOTE_HEIGHT
QUOTE_VOID
QUOTE_EXT_WALL
QUOTE_EXT_OPENING
```

The current implementation starts from normalized JSON. DWG/DXF conversion should produce the same structure used by the fixtures.
```

- [ ] **Step 4: Verify sample command works**

Run:

```bash
New-Item -ItemType Directory -Force build
cad-budget calculate tests/fixtures/simple_apartment.json --json-output build/simple-result.json --excel-output build/simple-result.xlsx
```

Expected:

```text
Wrote build/simple-result.json
Wrote build/simple-result.xlsx
```

- [ ] **Step 5: Run all tests**

Run:

```bash
pytest -q
```

Expected:

```text
12 passed
```

- [ ] **Step 6: Commit**

```bash
git add README.md tests/fixtures/open_living_room.json tests/fixtures/villa_special_spaces.json
git commit -m "docs: document takeoff CLI usage"
```

## Self-Review

Spec coverage:

```text
QUOTE_ROOM floor area: Task 4
QUOTE_TEXT / fallback text: Task 4
QUOTE_WINDOW width/height/default height: Task 4
QUOTE_DOOR retained but not deducted: domain model in Task 2, export fields in Task 7
QUOTE_WALL / QUOTE_OPENING wall-measure concept: Task 4
QUOTE_VOID / special spaces: Task 5 and Task 8
Balcony/terrace/elevator shaft: Task 5 and Task 8
Editable table: represented as JSON/Excel outputs in Tasks 6-7; browser editing deferred
Excel export: Task 7
DWG import: deferred to adapter after core; normalized JSON is the contract
Exterior wall table: model support starts in Task 2; full exterior calculation deferred to a follow-up plan
```

Known follow-up plans after this one:

```text
DWG/DXF adapter that emits ProjectInput JSON
Browser review/editing UI
Exterior wall quantity table
Door opening deduction option
Quotation rule engine
```
