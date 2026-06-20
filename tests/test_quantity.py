from cad_budget.models import (
    DataStatus,
    DoorMarker,
    HeightMode,
    HeightMarker,
    VoidMarker,
    SpaceType,
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


def test_wall_lines_infer_open_boundary_without_opening_marker():
    project = ProjectInput(
        project_name="Wall Derived Opening",
        default_height=2.8,
        rooms=[RoomBoundary(id="living", points=rect(0, 0, 4, 3), name="Living")],
        walls=[
            PolylineMarker(
                id="bottom",
                layer=LayerName.QUOTE_WALL,
                points=[Point(x=0, y=0), Point(x=4, y=0)],
            ),
            PolylineMarker(
                id="top",
                layer=LayerName.QUOTE_WALL,
                points=[Point(x=0, y=3), Point(x=4, y=3)],
            ),
            PolylineMarker(
                id="left",
                layer=LayerName.QUOTE_WALL,
                points=[Point(x=0, y=0), Point(x=0, y=3)],
            ),
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.floor_perimeter == 14
    assert row.open_boundary_length == 3
    assert row.wall_measure_perimeter == 11
    assert row.gross_wall_area == 30.8


def test_floorless_opening_for_floored_rooms_is_flagged_as_floor_mismatch():
    project = ProjectInput(
        project_name="Stacked Openings",
        default_height=2.8,
        rooms=[
            RoomBoundary(id="r1", floor="1F", points=rect(0, 0, 4, 3)),
            RoomBoundary(id="r2", floor="2F", points=rect(4, 0, 8, 3)),
        ],
        openings=[
            PolylineMarker(
                id="global-open",
                layer=LayerName.QUOTE_OPENING,
                points=[Point(x=4, y=0), Point(x=4, y=3)],
            ),
        ],
    )

    result = calculate_quantities(project)
    room1, room2 = result.rows
    assert room1.status is DataStatus.NEEDS_REVIEW
    assert room2.status is DataStatus.NEEDS_REVIEW
    assert room1.open_boundary_length == 0
    assert room2.open_boundary_length == 0
    assert any(
        exc.code == "marker_floor_mismatch_opening" for exc in result.exceptions if exc.room_id == "r1"
    )
    assert any(
        exc.code == "marker_floor_mismatch_opening" for exc in result.exceptions if exc.room_id == "r2"
    )
    assert any(
        "marker_floor_mismatch_opening" in note for note in room1.exception_notes
    )
    assert any(
        "marker_floor_mismatch_opening" in note for note in room2.exception_notes
    )

    floor_project = ProjectInput(
        project_name="Scoped Floor Opening",
        default_height=2.8,
        rooms=[
            RoomBoundary(id="r1", floor="1F", points=rect(0, 0, 4, 3)),
            RoomBoundary(id="r2", floor="2F", points=rect(4, 0, 8, 3)),
        ],
        openings=[
            PolylineMarker(
                id="floor1-open",
                layer=LayerName.QUOTE_OPENING,
                points=[Point(x=4, y=0), Point(x=4, y=3)],
                floor="1F",
            )
        ],
    )

    scoped_result = calculate_quantities(floor_project)
    room1, room2 = scoped_result.rows
    assert room1.open_boundary_length == 3
    assert room2.open_boundary_length == 0


def test_oversized_window_exceeds_wall_area_and_flags_review():
    project = ProjectInput(
        project_name="Oversized Window",
        rooms=[RoomBoundary(id="tiny", points=rect(0, 0, 2, 2), name="Tiny Room")],
        windows=[WindowMarker(id="w1", point=Point(x=1, y=1), width=10.0, height=3.0)],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.room_name == "Tiny Room"
    assert row.gross_wall_area == 22.4
    assert row.window_area == 30.0
    assert row.net_wall_area == 0
    assert row.status is DataStatus.NEEDS_REVIEW
    assert any(
        exc.code == "window_area_exceeds_wall_area" and exc.room_id == "tiny"
        for exc in result.exceptions
    )
    assert any(
        "window_area_exceeds_wall_area" in note
        for note in row.exception_notes
    )


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


def test_window_marker_near_exterior_boundary_is_assigned_to_room():
    project = ProjectInput(
        project_name="Exterior Window",
        default_height=2.8,
        rooms=[RoomBoundary(id="room", points=rect(0, 0, 4, 3), name="Room")],
        windows=[WindowMarker(id="win", point=Point(x=2, y=-0.12), width=1.2, height=1.5)],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.window_count == 1
    assert row.window_area == 1.8
    assert not any(exc.code == "ambiguous_window_assignment" for exc in result.exceptions)


def test_shared_boundary_door_is_counted_for_each_adjacent_room():
    project = ProjectInput(
        project_name="Adjacent Door Rooms",
        default_height=2.8,
        rooms=[
            RoomBoundary(id="left", points=rect(0, 0, 4, 3), name="Left"),
            RoomBoundary(id="right", points=rect(4, 0, 8, 3), name="Right"),
        ],
        doors=[
            DoorMarker(id="shared", point=Point(x=4, y=1), width=0.9, height=2.1),
        ],
    )

    result = calculate_quantities(project)

    left, right = result.rows
    assert left.door_opening_count == 1
    assert right.door_opening_count == 1
    assert left.door_opening_area == 1.89
    assert right.door_opening_area == 1.89
    assert not any(exception.code == "ambiguous_door_assignment" for exception in result.exceptions)


def test_door_marker_near_exterior_boundary_is_assigned_to_room():
    project = ProjectInput(
        project_name="Exterior Door",
        default_height=2.8,
        rooms=[RoomBoundary(id="room", points=rect(0, 0, 4, 3), name="Room")],
        doors=[DoorMarker(id="door", point=Point(x=2, y=-0.12), width=0.9, height=2.1)],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.door_opening_count == 1
    assert row.door_opening_area == 1.89
    assert not any(exc.code == "ambiguous_door_assignment" for exc in result.exceptions)


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


def test_door_with_width_and_height_reports_opening_area_without_reducing_net_wall_area():
    project = ProjectInput(
        project_name="Door Area",
        default_height=2.8,
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3), name="Bedroom")],
        windows=[WindowMarker(id="win1", point=Point(x=1, y=1), width=1.0, height=1.0)],
        doors=[DoorMarker(id="door1", point=Point(x=2, y=1), width=0.9, height=2.1)],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.door_opening_count == 1
    assert row.door_opening_area == 1.89
    assert row.gross_wall_area == 39.2
    assert row.window_area == 1.0
    assert row.net_wall_area == 38.2


def test_door_with_width_only_reports_count_and_zero_area():
    project = ProjectInput(
        project_name="Door Width Only",
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3), name="Bedroom")],
        doors=[DoorMarker(id="door1", point=Point(x=2, y=1), width=0.9)],
    )

    result = calculate_quantities(project)

    row = result.rows[0]
    assert row.door_opening_count == 1
    assert row.door_opening_area == 0.0


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
        windows=[WindowMarker(id="win1", point=Point(x=1, y=1), width=1.2)],
    )

    row = calculate_quantities(project).rows[0]

    assert row.status.value == "excluded"
    assert row.height == 2.8
    assert row.floor_area == 0
    assert row.wall_measure_perimeter == 0
    assert row.open_boundary_length == 0
    assert row.gross_wall_area == 0
    assert row.window_count == 0
    assert row.window_area == 0
    assert row.door_opening_count == 0
    assert row.door_opening_area == 0
    assert row.net_wall_area == 0
    assert row.include_in_floor_quantity is False
    assert row.include_in_wall_paint_quantity is False


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


def test_void_space_uses_void_marker_height_when_no_room_height():
    project = ProjectInput(
        project_name="Lobby Void",
        rooms=[
            RoomBoundary(
                id="void-atrium",
                points=rect(0, 0, 6, 4),
                space_type=SpaceType.VOID,
                floor="2F",
            )
        ],
        voids=[
            VoidMarker(
                id="void-marker",
                points=rect(1, 1, 5, 3),
                height=5.8,
                floor="2F",
            )
        ],
    )

    row = calculate_quantities(project).rows[0]

    assert row.space_type is SpaceType.VOID
    assert row.height == 5.8


def test_void_opening_is_excluded_from_floor_and_wall_quantities():
    project = ProjectInput(
        project_name="Void Opening",
        rooms=[
            RoomBoundary(id="floor-room", points=rect(0, 0, 4, 3)),
            RoomBoundary(
                id="void-opening",
                points=rect(0, 0, 4, 3),
                floor="2F",
                space_type=SpaceType.VOID_OPENING,
            ),
        ],
    )

    result = calculate_quantities(project)
    row_opening = result.rows[1]
    assert row_opening.space_type is SpaceType.VOID_OPENING
    assert row_opening.status is DataStatus.EXCLUDED
    assert row_opening.floor_area == 0
    assert row_opening.wall_measure_perimeter == 0
    assert row_opening.open_boundary_length == 0
    assert row_opening.gross_wall_area == 0
    assert row_opening.net_wall_area == 0
    assert row_opening.include_in_floor_quantity is False
    assert row_opening.include_in_wall_paint_quantity is False


def test_balcony_opening_reduces_wall_measure_perimeter():
    project = ProjectInput(
        project_name="Balcony Opening",
        rooms=[
            RoomBoundary(
                id="balcony",
                points=rect(0, 0, 3, 1.5),
                space_type=SpaceType.BALCONY,
                include_in_wall_paint_quantity=False,
            )
        ],
        openings=[
            PolylineMarker(
                id="balcony-open",
                layer=LayerName.QUOTE_OPENING,
                points=[Point(x=3, y=0), Point(x=3, y=1.5)],
            )
        ],
    )

    row = calculate_quantities(project).rows[0]

    assert row.space_type is SpaceType.BALCONY
    assert row.floor_perimeter == 9
    assert row.open_boundary_length == 1.5
    assert row.wall_measure_perimeter == 7.5


def test_void_space_with_ambiguous_void_markers_falls_back_to_normal_height():
    project = ProjectInput(
        project_name="Ambiguous Void",
        floor_heights={"1F": 3.1},
        rooms=[
            RoomBoundary(
                id="void-1",
                name="Voidded",
                points=rect(0, 0, 5, 3),
                floor="1F",
                space_type=SpaceType.VOID,
            )
        ],
        voids=[
            VoidMarker(
                id="void-high",
                points=[Point(x=1, y=1), Point(x=4, y=1)],
                height=6.0,
                floor="1F",
            ),
            VoidMarker(
                id="void-mid",
                points=[Point(x=4.5, y=1), Point(x=4.8, y=1)],
                height=4.0,
                floor="1F",
            ),
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.space_type is SpaceType.VOID
    assert row.height == 3.1
    assert row.height_mode is HeightMode.FLOOR_DEFAULT
    assert row.status is DataStatus.NEEDS_REVIEW
    assert any(
        exc.code == "ambiguous_void_marker" and exc.room_id == "void-1"
        for exc in result.exceptions
    )


def test_void_marker_matching_multiple_void_rooms_is_ambiguous_for_each_room():
    project = ProjectInput(
        project_name="Shared Void Marker",
        floor_heights={"1F": 3.1},
        rooms=[
            RoomBoundary(
                id="void-left",
                name="Left Void",
                points=rect(0, 0, 4, 3),
                floor="1F",
                space_type=SpaceType.VOID,
            ),
            RoomBoundary(
                id="void-right",
                name="Right Void",
                points=rect(4, 0, 8, 3),
                floor="1F",
                space_type=SpaceType.VOID,
            ),
        ],
        voids=[
            VoidMarker(
                id="shared-void-marker",
                points=[Point(x=4, y=0.5), Point(x=4, y=2.5)],
                height=6.2,
                floor="1F",
            )
        ],
    )

    result = calculate_quantities(project)
    left, right = result.rows

    assert left.height == 3.1
    assert right.height == 3.1
    assert left.status is DataStatus.NEEDS_REVIEW
    assert right.status is DataStatus.NEEDS_REVIEW
    assert any("shared-void-marker" in note for note in left.exception_notes)
    assert any("shared-void-marker" in note for note in right.exception_notes)
    assert {
        exc.room_id
        for exc in result.exceptions
        if exc.code == "ambiguous_void_marker"
    } == {"void-left", "void-right"}


def test_void_space_related_floors_missing_floor_height_triggers_exception():
    project = ProjectInput(
        project_name="Void Missing Floors",
        floor_heights={"1F": 3.1},
        rooms=[
            RoomBoundary(
                id="void-missing",
                name="Missing Floor Void",
                points=rect(0, 0, 5, 3),
                floor="1F",
                space_type=SpaceType.VOID,
            )
        ],
        voids=[
            VoidMarker(
                id="void-mix",
                points=[Point(x=1, y=1), Point(x=4, y=1)],
                related_floors=["1F", "2F"],
                floor="1F",
            )
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.height == 3.1
    assert row.status is DataStatus.NEEDS_REVIEW
    assert any(
        exc.code == "void_related_floor_height_missing" and exc.room_id == "void-missing"
        for exc in result.exceptions
    )


def test_void_space_related_floor_sum_sets_related_floors_sum_mode():
    project = ProjectInput(
        project_name="Void Related Sum",
        floor_heights={"1F": 3.0, "2F": 2.8},
        rooms=[
            RoomBoundary(
                id="void-sum",
                name="Summed Void",
                points=rect(0, 0, 5, 3),
                floor="2F",
                space_type=SpaceType.VOID,
            )
        ],
        voids=[
            VoidMarker(
                id="void-sum",
                points=[Point(x=1, y=1), Point(x=4, y=1)],
                related_floors=["1F", "2F"],
                floor="2F",
            )
        ],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.space_type is SpaceType.VOID
    assert row.height == 5.8
    assert row.height_mode is HeightMode.RELATED_FLOORS_SUM


def test_floorless_markers_for_floored_room_are_ignored_and_flagged():
    project = ProjectInput(
        project_name="Floor-Mismatch Marker",
        default_height=2.8,
        floor_heights={"1F": 2.9},
        rooms=[RoomBoundary(id="r1", floor="1F", points=rect(0, 0, 4, 3))],
        texts=[TextMarker(id="t1", text="Bedroom", point=Point(x=2, y=1))],
        windows=[WindowMarker(id="w1", point=Point(x=1, y=1), width=1.2)],
        doors=[DoorMarker(id="d1", point=Point(x=2, y=1), width=0.9)],
        heights=[HeightMarker(id="h1", point=Point(x=3, y=1), height=4.8)],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.room_name == "\u672a\u547d\u540d\u7a7a\u95f4"
    assert row.height == 2.9
    assert row.height_mode is HeightMode.FLOOR_DEFAULT
    assert row.window_count == 0
    assert row.window_area == 0
    assert row.door_opening_count == 0
    assert row.status is DataStatus.NEEDS_REVIEW
    assert {exc.code for exc in result.exceptions if exc.room_id == "r1"} >= {
        "marker_floor_mismatch_text",
        "marker_floor_mismatch_window",
        "marker_floor_mismatch_door",
        "marker_floor_mismatch_height",
    }


def test_explicit_height_markers_for_same_room_id_become_ambiguous():
    project = ProjectInput(
        project_name="Duplicate Explicit Heights",
        default_height=2.8,
        rooms=[RoomBoundary(id="r1", points=rect(0, 0, 4, 3))],
        heights=[
            HeightMarker(id="h1", point=Point(x=1, y=1), height=2.5, room_id="r1"),
            HeightMarker(id="h2", point=Point(x=3, y=2), height=3.1, room_id="r1"),
        ],
        texts=[TextMarker(id="t1", text="Bedroom", point=Point(x=2, y=1))],
    )

    result = calculate_quantities(project)
    row = result.rows[0]

    assert row.height == 2.8
    assert row.height_mode is HeightMode.PROJECT_DEFAULT
    assert row.status is DataStatus.NEEDS_REVIEW
    assert any(
        exc.code == "ambiguous_height_assignment" and exc.room_id == "r1"
        for exc in result.exceptions
    )
