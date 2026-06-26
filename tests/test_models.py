from cad_budget.models import (
    ConstructionKind,
    ConstructionMarker,
    DataStatus,
    FixtureKind,
    FixtureMarker,
    HeightMode,
    LayerName,
    Point,
    ProjectInput,
    PolylineMarker,
    QuantityRow,
    RoomBoundary,
    SpaceType,
    VoidMarker,
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


def test_project_input_accepts_custom_and_cabinet_fixture_markers():
    project = ProjectInput(
        project_name="Fixtures",
        custom_items=[
            FixtureMarker(
                id="custom-1",
                layer=LayerName.QUOTE_CUSTOM,
                kind=FixtureKind.CUSTOM,
                points=[Point(x=0, y=0), Point(x=2, y=0)],
                length=2.0,
                height=2.6,
                fixture_type="衣柜",
            )
        ],
        cabinet_items=[
            FixtureMarker(
                id="cabinet-1",
                layer=LayerName.QUOTE_CABINET,
                kind=FixtureKind.CABINET,
                points=[Point(x=0, y=1), Point(x=3, y=1)],
                length=3.0,
                fixture_type="地柜",
            )
        ],
    )

    assert project.custom_items[0].kind is FixtureKind.CUSTOM
    assert project.cabinet_items[0].fixture_type == "地柜"


def test_layer_name_includes_explicit_cabinet_type_layers():
    assert LayerName.QUOTE_BASE_CABINET.value == "QUOTE_BASE_CABINET"
    assert LayerName.QUOTE_WALL_CABINET.value == "QUOTE_WALL_CABINET"


def test_project_input_accepts_background_wall_markers():
    project = ProjectInput(
        project_name="Background Wall",
        background_walls=[
            ConstructionMarker(
                id="background-1",
                layer=LayerName.QUOTE_BACKGROUND_WALL,
                kind=ConstructionKind.BACKGROUND_WALL,
                points=[Point(x=0, y=0), Point(x=3, y=0)],
                length=3.0,
                height=2.4,
            )
        ],
    )

    assert project.background_walls[0].kind is ConstructionKind.BACKGROUND_WALL


def test_project_input_accepts_shower_glass_markers():
    project = ProjectInput(
        project_name="Shower Glass",
        shower_glasses=[
            ConstructionMarker(
                id="shower-glass-1",
                layer=LayerName.QUOTE_SHOWER_GLASS,
                kind=ConstructionKind.SHOWER_GLASS,
                points=[Point(x=1, y=1)],
            )
        ],
    )

    assert project.shower_glasses[0].kind is ConstructionKind.SHOWER_GLASS


def test_project_input_accepts_wall_tile_markers():
    project = ProjectInput(
        project_name="Wall Tile",
        wall_tiles=[
            ConstructionMarker(
                id="balcony-wall-tile",
                layer=LayerName.QUOTE_WALL_TILE,
                kind=ConstructionKind.WALL_TILE,
                points=[Point(x=0, y=0), Point(x=3, y=0)],
                length=3.0,
            )
        ],
    )

    assert project.wall_tiles[0].kind is ConstructionKind.WALL_TILE


def test_quantity_row_fixture_details_default_to_empty_lists():
    row = QuantityRow(
        room_id="r1",
        floor=None,
        room_name="卧室",
        space_type=SpaceType.NORMAL,
        height=2.8,
        height_mode=HeightMode.PROJECT_DEFAULT,
        floor_area=10,
        floor_perimeter=12,
        wall_measure_perimeter=12,
        open_boundary_length=0,
        gross_wall_area=33.6,
        window_count=0,
        window_area=0,
        door_opening_count=0,
        door_opening_area=0,
        net_wall_area=33.6,
        is_outdoor=False,
        include_in_floor_quantity=True,
        include_in_wall_paint_quantity=True,
        status=DataStatus.CONFIRMED,
    )

    assert row.custom_details == []
    assert row.cabinet_details == []


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


def test_void_marker_rejects_empty_points():
    with pytest.raises(ValidationError):
        VoidMarker(
            id="void-empty",
            points=[],
        )
