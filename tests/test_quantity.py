from cad_budget.models import (
    DataStatus,
    HeightMarker,
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
        texts=[TextMarker(id="t1", text="Bedroom", point=Point(x=2, y=1))],
        walls=[PolylineMarker(id="w1", layer=LayerName.QUOTE_WALL, points=rect(0, 0, 4, 3))],
        windows=[WindowMarker(id="win1", point=Point(x=2, y=0), width=1.2, height=1.5)],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.room_name == "Bedroom"
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
        texts=[TextMarker(id="t1", text="Living", point=Point(x=2, y=1))],
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


def test_identical_floor_footprints_match_markers_only_on_the_same_floor():
    project = ProjectInput(
        project_name="Stacked Rooms",
        default_height=2.8,
        floor_heights={"1F": 3.2, "2F": 3.9},
        rooms=[
            RoomBoundary(id="r1", floor="1F", points=rect(0, 0, 4, 3)),
            RoomBoundary(id="r2", floor="2F", points=rect(0, 0, 4, 3)),
        ],
        texts=[
            TextMarker(id="t1", text="Room-1F", point=Point(x=2, y=1), floor="1F"),
            TextMarker(id="t2", text="Room-2F", point=Point(x=2, y=1), floor="2F"),
        ],
        windows=[
            WindowMarker(id="w1", point=Point(x=1, y=1), width=0.6, height=1.0, floor="1F"),
            WindowMarker(id="w2", point=Point(x=1, y=1), width=0.6, height=1.0, floor="2F"),
        ],
        heights=[
            HeightMarker(id="h1", point=Point(x=2, y=1), height=2.7, floor="1F"),
            HeightMarker(id="h2", point=Point(x=2, y=1), height=3.4, floor="2F"),
        ],
    )

    result = calculate_quantities(project)

    r1, r2 = result.rows
    assert r1.room_name == "Room-1F"
    assert r2.room_name == "Room-2F"
    assert r1.window_area == 0.6
    assert r2.window_area == 0.6
    assert r1.height == 2.7
    assert r2.height == 3.4


def test_shared_boundary_window_is_ambiguous_and_not_counted():
    project = ProjectInput(
        project_name="Adjacent Rooms",
        default_height=2.8,
        rooms=[
            RoomBoundary(id="left", points=rect(0, 0, 4, 3)),
            RoomBoundary(id="right", points=rect(4, 0, 8, 3)),
        ],
        texts=[
            TextMarker(id="t1", text="Left", point=Point(x=2, y=1)),
            TextMarker(id="t2", text="Right", point=Point(x=6, y=1)),
        ],
        windows=[
            WindowMarker(id="shared", point=Point(x=4, y=1), width=1.2),
        ],
    )

    result = calculate_quantities(project)

    left, right = result.rows
    assert left.window_count == 0
    assert right.window_count == 0
    assert left.window_area == 0
    assert right.window_area == 0
    assert left.status is DataStatus.NEEDS_REVIEW
    assert right.status is DataStatus.NEEDS_REVIEW
    assert any(
        exception.code == "ambiguous_window_assignment" and exception.room_id in {"left", "right"}
        for exception in result.exceptions
    )


def test_missing_room_name_is_defaulted_and_needs_review():
    project = ProjectInput(
        project_name="Missing Name",
        default_height=2.8,
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3))],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.room_name == "未命名空间"
    assert row.status is DataStatus.NEEDS_REVIEW
    assert any(exception.code == "room_has_no_name" for exception in result.exceptions)


def test_missing_window_height_uses_project_default_and_marks_default_inferred():
    project = ProjectInput(
        project_name="Window Defaulted",
        default_height=2.8,
        default_window_height=1.7,
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3))],
        texts=[TextMarker(id="t1", text="Bedroom", point=Point(x=2, y=1))],
        windows=[WindowMarker(id="win1", point=Point(x=1, y=1), width=1.2)],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.window_area == 2.04
    assert row.status is DataStatus.DEFAULT_INFERRED
    assert any("default height" in note for note in row.exception_notes)
    assert any(exception.code == "window_height_defaulted" for exception in result.exceptions)
