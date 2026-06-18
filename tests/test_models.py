from cad_budget.models import (
    DataStatus,
    HeightMode,
    LayerName,
    Point,
    ProjectInput,
    PolylineMarker,
    RoomBoundary,
    SpaceType,
)
from pydantic import ValidationError
import pytest


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


def test_room_boundary_rejects_non_closed_polygon():
    with pytest.raises(ValidationError):
        RoomBoundary(
            id="room-2",
            points=[
                Point(x=0, y=0),
                Point(x=4, y=0),
                Point(x=4, y=3),
                Point(x=0, y=3),
            ],
            floor="1F",
            space_type=SpaceType.NORMAL,
        )


def test_polyline_marker_rejects_single_point():
    with pytest.raises(ValidationError):
        PolylineMarker(
            id="line-1",
            layer=LayerName.QUOTE_WALL,
            points=[Point(x=1, y=1)],
        )
