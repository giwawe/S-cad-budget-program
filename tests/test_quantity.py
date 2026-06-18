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
