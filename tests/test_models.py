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
