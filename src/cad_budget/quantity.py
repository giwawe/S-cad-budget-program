from __future__ import annotations

from collections import defaultdict
from math import hypot
from typing import Any

from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.geometry import closed_polygon_area, closed_polygon_perimeter, point_inside_polygon
from cad_budget.models import VoidMarker
from cad_budget.models import (
    ConstructionKind,
    ConstructionMarker,
    ConstructionQuantityDetail,
    DataStatus,
    DoorQuantityDetail,
    ExteriorQuantityRow,
    FixtureKind,
    FixtureMarker,
    FixturePricingMode,
    FixtureQuantityDetail,
    HeightMode,
    LayerName,
    ProjectInput,
    QuantityException,
    QuantityResult,
    QuantityRow,
    RoomBoundary,
    SpaceType,
    WindowQuantityDetail,
)


_MARKER_ASSIGNMENT_TOLERANCE_METERS = 0.3
_WALL_BOUNDARY_TOLERANCE_METERS = 0.1
_WALL_PARALLEL_CROSS_TOLERANCE = 0.1
_DEFAULT_DOOR_DETAIL_HEIGHT_METERS = 2.1
_DEFAULT_CUSTOM_HEIGHT_METERS = 2.6
_LOW_CUSTOM_HEIGHT_THRESHOLD_METERS = 1.0


def _quote_include_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"false", "0", "no", "n", "off"}:
            return False
        if cleaned in {"true", "1", "yes", "y", "on"}:
            return True
    return True


def _polyline_marker_length(marker: ConstructionMarker) -> float:
    if marker.length > 0:
        return marker.length
    return round(
        sum(
            hypot(following.x - current.x, following.y - current.y)
            for current, following in zip(marker.points, marker.points[1:])
        ),
        6,
    )


def _construction_effective_height(project: ProjectInput, marker: ConstructionMarker) -> tuple[float | None, bool]:
    if marker.height is not None:
        return marker.height, False
    if marker.floor and marker.floor in project.floor_heights:
        return project.floor_heights[marker.floor], True
    return project.default_height, True


def _floor_compatible(room_floor: str | None, marker_floor: str | None) -> bool:
    return room_floor == marker_floor


def _marker_point_matches_room(point, room: RoomBoundary) -> bool:
    polygon = _room_polygon(room)
    marker_point = ShapelyPoint(point.x, point.y)
    return bool(polygon.covers(marker_point)) or polygon.distance(marker_point) <= _MARKER_ASSIGNMENT_TOLERANCE_METERS


def _resolve_room_names(project: ProjectInput, rooms: list[RoomBoundary]) -> tuple[dict[str, str], list[QuantityException]]:
    assignments: dict[str, str] = {}
    exceptions: list[QuantityException] = []
    matched_names: dict[str, list[str]] = defaultdict(list)

    for text in project.texts:
        matched_room_ids: list[str] = []
        for room in rooms:
            if room.name:
                continue
            if not point_inside_polygon(text.point, room.points):
                continue
            if _floor_compatible(room.floor, text.floor):
                matched_room_ids.append(room.id)
            else:
                exceptions.append(
                    QuantityException(
                        code="marker_floor_mismatch_text",
                        message=f"Text {text.id} skipped for room {room.id} due floor mismatch",
                        room_id=room.id,
                    )
                )

        if len(matched_room_ids) > 1:
            for room_id in matched_room_ids:
                exceptions.append(
                    QuantityException(
                        code="ambiguous_room_text",
                        message=f"Text {text.id} matches multiple rooms",
                        room_id=room_id,
                    )
                )
            continue

        if len(matched_room_ids) == 1:
            matched_names[matched_room_ids[0]].append(text.text)

    for room_id, names in matched_names.items():
        if len(names) == 1:
            assignments[room_id] = names[0]
        else:
            exceptions.append(
                QuantityException(
                    code="multiple_room_names",
                    message=f"Room {room_id} contains multiple names: {', '.join(names)}",
                    room_id=room_id,
                )
            )

    return assignments, exceptions


def _resolve_height_assignments(
    project: ProjectInput, rooms: list[RoomBoundary]
) -> tuple[dict[str, tuple[float, HeightMode]], list[QuantityException]]:
    assigned: dict[str, tuple[float, HeightMode]] = {}
    exceptions: list[QuantityException] = []

    explicit_by_room: dict[str, list[tuple[float, str]]] = defaultdict(list)
    point_candidates: dict[str, list[tuple[float, str]]] = defaultdict(list)

    for marker in project.heights:
        if marker.room_id:
            for room in rooms:
                if room.id != marker.room_id:
                    continue
                if not _floor_compatible(room.floor, marker.floor):
                    exceptions.append(
                        QuantityException(
                            code="marker_floor_mismatch_height",
                            message=f"Height marker {marker.id} skipped for room {room.id} due floor mismatch",
                            room_id=room.id,
                        )
                    )
                    continue
                explicit_by_room[room.id].append((marker.height, marker.id))
            continue

        candidate_rooms: list[str] = []
        for room in rooms:
            if not point_inside_polygon(marker.point, room.points):
                continue
            if _floor_compatible(room.floor, marker.floor):
                candidate_rooms.append(room.id)
            else:
                exceptions.append(
                    QuantityException(
                        code="marker_floor_mismatch_height",
                        message=f"Height marker {marker.id} skipped for room {room.id} due floor mismatch",
                        room_id=room.id,
                    )
                )
        if len(candidate_rooms) == 1:
            point_candidates[candidate_rooms[0]].append((marker.height, marker.id))
        elif len(candidate_rooms) > 1:
            for room_id in candidate_rooms:
                exceptions.append(
                    QuantityException(
                        code="ambiguous_height_assignment",
                        message=f"Height marker {marker.id} matches multiple rooms",
                        room_id=room_id,
                    )
                )

    for room in rooms:
        if room.id in explicit_by_room:
            heights = explicit_by_room[room.id]
            if len(heights) == 1:
                assigned[room.id] = (heights[0][0], HeightMode.QUOTE_HEIGHT)
            elif len(heights) > 1:
                marker_ids = ", ".join(marker_id for _, marker_id in heights)
                exceptions.append(
                    QuantityException(
                        code="ambiguous_height_assignment",
                        message=f"Room {room.id} has multiple explicit heights: {marker_ids}",
                        room_id=room.id,
                    )
                )
            continue

        candidates = point_candidates.get(room.id, [])
        if len(candidates) == 1:
            height = candidates[0][0]
            assigned[room.id] = (height, HeightMode.QUOTE_HEIGHT)
        elif len(candidates) > 1:
            marker_ids = ", ".join(marker_id for _, marker_id in candidates)
            exceptions.append(
                QuantityException(
                    code="ambiguous_height_assignment",
                    message=f"Room {room.id} has multiple height points: {marker_ids}",
                    room_id=room.id,
                )
            )

    return assigned, exceptions


def _resolve_window_assignments(
    project: ProjectInput, rooms: list[RoomBoundary]
) -> tuple[dict[str, list[Any]], list[QuantityException]]:
    assignments: dict[str, list] = defaultdict(list)
    exceptions: list[QuantityException] = []

    for window in project.windows:
        matched_room_ids: list[str] = []
        for room in rooms:
            if not _marker_point_matches_room(window.point, room):
                continue
            if _floor_compatible(room.floor, window.floor):
                matched_room_ids.append(room.id)
            else:
                exceptions.append(
                    QuantityException(
                        code="marker_floor_mismatch_window",
                        message=f"Window {window.id} skipped for room {room.id} due floor mismatch",
                        room_id=room.id,
                    )
                )
        if len(matched_room_ids) == 1:
            assignments[matched_room_ids[0]].append(window)
        elif len(matched_room_ids) > 1:
            for room_id in matched_room_ids:
                exceptions.append(
                    QuantityException(
                        code="ambiguous_window_assignment",
                        message=f"Window {window.id} matches multiple rooms",
                        room_id=room_id,
                    )
                )

    return assignments, exceptions


def _resolve_door_assignments(
    project: ProjectInput, rooms: list[RoomBoundary]
) -> tuple[dict[str, list[Any]], list[QuantityException]]:
    assignments: dict[str, list] = defaultdict(list)
    exceptions: list[QuantityException] = []

    for door in project.doors:
        matched_room_ids: list[str] = []
        for room in rooms:
            if not _marker_point_matches_room(door.point, room):
                continue
            if _floor_compatible(room.floor, door.floor):
                matched_room_ids.append(room.id)
            else:
                exceptions.append(
                    QuantityException(
                        code="marker_floor_mismatch_door",
                        message=f"Door {door.id} skipped for room {room.id} due floor mismatch",
                        room_id=room.id,
                    )
                )
        for room_id in matched_room_ids:
            assignments[room_id].append(door)

    return assignments, exceptions


def _fixture_midpoint(fixture: FixtureMarker) -> ShapelyPoint | None:
    if len(fixture.points) < 2:
        return None
    start = fixture.points[0]
    end = fixture.points[-1]
    return ShapelyPoint((start.x + end.x) / 2, (start.y + end.y) / 2)


def _fixture_room_attribute(fixture: FixtureMarker) -> str | None:
    for key in ("ROOM", "room"):
        value = fixture.attributes.get(key)
        if value is not None:
            return str(value)
    return None


def _is_excluded_area_space(room: RoomBoundary) -> bool:
    return room.space_type in {SpaceType.ELEVATOR_SHAFT, SpaceType.VOID_OPENING}


def _assign_fixture_to_room(
    assignments: dict[str, list[FixtureMarker]],
    exceptions: list[QuantityException],
    room: RoomBoundary,
    fixture: FixtureMarker,
) -> None:
    assignments[room.id].append(fixture)
    if _is_excluded_area_space(room):
        exceptions.append(
            QuantityException(
                code="fixture_marker_in_excluded_room",
                message=(
                    "fixture_marker_in_excluded_room: "
                    f"Fixture {fixture.id} assigned to excluded room {room.id}"
                ),
                room_id=room.id,
            )
        )


def _fixture_floor_mismatch_exception(fixture: FixtureMarker, room: RoomBoundary) -> QuantityException:
    return QuantityException(
        code="marker_floor_mismatch_fixture",
        message=(
            "marker_floor_mismatch_fixture: "
            f"Fixture {fixture.id} skipped for room {room.id} due floor mismatch"
        ),
        room_id=room.id,
    )


def _fixture_outside_tolerance_exception(
    fixture: FixtureMarker,
    room_id: str | None,
    distance: float | None,
) -> QuantityException:
    distance_text = "unknown" if distance is None else round(distance, 6)
    return QuantityException(
        code="fixture_marker_outside_assignment_tolerance",
        message=(
            "fixture_marker_outside_assignment_tolerance: "
            f"Fixture {fixture.id} is outside fixture assignment tolerance; nearest distance {distance_text}"
        ),
        room_id=room_id,
    )


def _fixture_unmatched_exception(fixture: FixtureMarker) -> QuantityException:
    return QuantityException(
        code="fixture_marker_unmatched",
        message=f"fixture_marker_unmatched: Fixture {fixture.id} could not be assigned to any room",
    )


def _resolve_fixture_assignments(
    rooms: list[RoomBoundary],
    fixtures: list[FixtureMarker],
    room_names: dict[str, str],
) -> tuple[dict[str, list[FixtureMarker]], list[QuantityException]]:
    assignments: dict[str, list[FixtureMarker]] = defaultdict(list)
    exceptions: list[QuantityException] = []

    for fixture in fixtures:
        assigned_by_room_id = False
        explicitly_floor_mismatched = False
        if fixture.room_id is not None:
            for room in rooms:
                if room.id != fixture.room_id:
                    continue
                if _floor_compatible(room.floor, fixture.floor):
                    _assign_fixture_to_room(assignments, exceptions, room, fixture)
                    assigned_by_room_id = True
                    break
                exceptions.append(_fixture_floor_mismatch_exception(fixture, room))
                explicitly_floor_mismatched = True
                break
            if assigned_by_room_id:
                continue
            if explicitly_floor_mismatched:
                continue

        room_attribute = _fixture_room_attribute(fixture)
        if room_attribute is not None:
            assigned_by_attribute = False
            for room in rooms:
                room_name = room_names.get(room.id)
                if room.id != room_attribute and room_name != room_attribute:
                    continue
                if _floor_compatible(room.floor, fixture.floor):
                    _assign_fixture_to_room(assignments, exceptions, room, fixture)
                    assigned_by_attribute = True
                    break
                exceptions.append(_fixture_floor_mismatch_exception(fixture, room))
                explicitly_floor_mismatched = True
                break
            if assigned_by_attribute:
                continue
            if explicitly_floor_mismatched:
                continue

        midpoint = _fixture_midpoint(fixture)
        if midpoint is None:
            exceptions.append(_fixture_unmatched_exception(fixture))
            continue

        covered_room_ids: list[str] = []
        floor_mismatch_rooms: list[RoomBoundary] = []
        nearest_room_id: str | None = None
        nearest_distance: float | None = None
        nearest_any_room_id: str | None = None
        nearest_any_distance: float | None = None
        for room in rooms:
            polygon = _room_polygon(room)
            if polygon.covers(midpoint):
                if not _floor_compatible(room.floor, fixture.floor):
                    floor_mismatch_rooms.append(room)
                    continue
                covered_room_ids.append(room.id)
                continue
            distance = float(polygon.boundary.distance(midpoint))
            if nearest_any_distance is None or distance < nearest_any_distance:
                nearest_any_room_id = room.id
                nearest_any_distance = distance
            if not _floor_compatible(room.floor, fixture.floor):
                if distance <= _MARKER_ASSIGNMENT_TOLERANCE_METERS:
                    floor_mismatch_rooms.append(room)
                continue
            if nearest_distance is None or distance < nearest_distance:
                nearest_room_id = room.id
                nearest_distance = distance

        if covered_room_ids:
            for room_id in covered_room_ids:
                room = next(room for room in rooms if room.id == room_id)
                _assign_fixture_to_room(assignments, exceptions, room, fixture)
        elif floor_mismatch_rooms:
            for room in floor_mismatch_rooms:
                exceptions.append(_fixture_floor_mismatch_exception(fixture, room))
        elif nearest_room_id is not None and nearest_distance is not None:
            if nearest_distance <= _MARKER_ASSIGNMENT_TOLERANCE_METERS:
                room = next(room for room in rooms if room.id == nearest_room_id)
                _assign_fixture_to_room(assignments, exceptions, room, fixture)
            else:
                exceptions.append(_fixture_outside_tolerance_exception(fixture, nearest_room_id, nearest_distance))
        elif nearest_any_room_id is not None:
            exceptions.append(
                _fixture_outside_tolerance_exception(fixture, nearest_any_room_id, nearest_any_distance)
            )
        else:
            exceptions.append(_fixture_unmatched_exception(fixture))

    return assignments, exceptions


def _custom_details_for_room(
    room: RoomBoundary,
    room_name: str,
    fixtures: list[FixtureMarker],
) -> list[FixtureQuantityDetail]:
    details: list[FixtureQuantityDetail] = []
    for fixture in fixtures:
        effective_height = fixture.height if fixture.height is not None else _DEFAULT_CUSTOM_HEIGHT_METERS
        height_defaulted = fixture.height is None
        if fixture.height is not None and effective_height < _LOW_CUSTOM_HEIGHT_THRESHOLD_METERS:
            pricing_mode = FixturePricingMode.LENGTH
            projected_area = 0.0
        else:
            pricing_mode = FixturePricingMode.PROJECTED_AREA
            projected_area = fixture.length * effective_height
        details.append(
            FixtureQuantityDetail(
                id=fixture.id,
                room_id=room.id,
                room_name=room_name,
                kind=FixtureKind.CUSTOM,
                length=round(fixture.length, 6),
                height=round(fixture.height, 6) if fixture.height is not None else None,
                effective_height=round(effective_height, 6),
                height_defaulted=height_defaulted,
                projected_area=round(projected_area, 6),
                pricing_mode=pricing_mode,
                fixture_type=fixture.fixture_type,
            )
        )
    return details


def _cabinet_details_for_room(
    room: RoomBoundary,
    room_name: str,
    fixtures: list[FixtureMarker],
) -> list[FixtureQuantityDetail]:
    return [
        FixtureQuantityDetail(
            id=fixture.id,
            room_id=room.id,
            room_name=room_name,
            kind=FixtureKind.CABINET,
            length=round(fixture.length, 6),
            height=round(fixture.height, 6) if fixture.height is not None else None,
            effective_height=round(fixture.height, 6) if fixture.height is not None else None,
            height_defaulted=False,
            projected_area=0.0,
            pricing_mode=FixturePricingMode.LENGTH,
            fixture_type=fixture.fixture_type,
        )
        for fixture in fixtures
    ]


def _resolve_void_height_assignments(
    project: ProjectInput, rooms: list[RoomBoundary]
) -> tuple[dict[str, tuple[float, HeightMode]], list[QuantityException]]:
    assigned: dict[str, tuple[float, HeightMode]] = {}
    exceptions: list[QuantityException] = []

    def _void_marker_matches_room(room: RoomBoundary, marker: VoidMarker) -> bool:
        if marker.floor is not None and room.floor is not None and marker.floor != room.floor:
            return False
        if marker.floor is not None and room.floor is None:
            return False
        if room.floor is not None and marker.related_floors and room.floor not in marker.related_floors:
            return False

        room_polygon = _room_polygon(room)
        if len(marker.points) > 1:
            marker_line = LineString((point.x, point.y) for point in marker.points)
            if not marker_line.is_empty and room_polygon.intersects(marker_line):
                return True

        return point_inside_polygon(marker.points[0], room.points)

    void_rooms = [room for room in rooms if room.space_type is SpaceType.VOID]
    markers_by_room: dict[str, list[tuple[int, VoidMarker]]] = defaultdict(list)
    rooms_by_marker: dict[int, list[RoomBoundary]] = defaultdict(list)
    ambiguous_exception_keys: set[tuple[str, str]] = set()

    for marker_index, marker in enumerate(project.voids):
        for room in void_rooms:
            if not _void_marker_matches_room(room, marker):
                continue
            markers_by_room[room.id].append((marker_index, marker))
            rooms_by_marker[marker_index].append(room)

    ambiguous_room_ids: set[str] = set()
    for marker_index, matched_rooms in rooms_by_marker.items():
        if len(matched_rooms) <= 1:
            continue

        marker = project.voids[marker_index]
        room_ids = ", ".join(room.id for room in matched_rooms)
        for room in matched_rooms:
            ambiguous_room_ids.add(room.id)
            exception_key = ("ambiguous_void_marker", room.id)
            if exception_key in ambiguous_exception_keys:
                continue
            ambiguous_exception_keys.add(exception_key)
            exceptions.append(
                QuantityException(
                    code="ambiguous_void_marker",
                    message=f"Void marker {marker.id} matches multiple rooms: {room_ids}",
                    room_id=room.id,
                )
            )

    for room in void_rooms:
        matching_markers = markers_by_room.get(room.id, [])
        if not matching_markers:
            continue

        if len(matching_markers) > 1:
            marker_ids = ", ".join(marker.id for _, marker in matching_markers)
            ambiguous_room_ids.add(room.id)
            exception_key = ("ambiguous_void_marker", room.id)
            if exception_key not in ambiguous_exception_keys:
                ambiguous_exception_keys.add(exception_key)
                exceptions.append(
                    QuantityException(
                        code="ambiguous_void_marker",
                        message=f"Room {room.id} matches multiple void markers: {marker_ids}",
                        room_id=room.id,
                    )
                )

        if room.id in ambiguous_room_ids:
            continue

        marker = matching_markers[0][1]
        if marker.height is not None:
            assigned[room.id] = (float(marker.height), HeightMode.QUOTE_VOID)
            continue

        if marker.related_floors:
            missing_floors = [floor_name for floor_name in marker.related_floors if floor_name not in project.floor_heights]
            if missing_floors:
                exceptions.append(
                    QuantityException(
                        code="void_related_floor_height_missing",
                        message=f"Void marker {marker.id} missing floor heights for: {', '.join(missing_floors)}",
                        room_id=room.id,
                    )
                )
                continue

            related_height_sum = sum(project.floor_heights[floor_name] for floor_name in marker.related_floors)
            assigned[room.id] = (round(related_height_sum, 6), HeightMode.RELATED_FLOORS_SUM)

    return assigned, exceptions


def _room_polygon(room: RoomBoundary) -> Polygon:
    return Polygon((point.x, point.y) for point in room.points)


def _nearest_room_segment_detail(point, room: RoomBoundary) -> tuple[str | None, float | None]:
    marker_point = ShapelyPoint(point.x, point.y)
    best_index: int | None = None
    best_length: float | None = None
    best_distance: float | None = None
    for index, (start, end) in enumerate(zip(room.points, room.points[1:])):
        segment = LineString([(start.x, start.y), (end.x, end.y)])
        length = float(segment.length)
        if length == 0:
            continue
        distance = float(segment.distance(marker_point))
        if best_distance is None or distance < best_distance:
            best_index = index
            best_length = length
            best_distance = distance
    if best_index is None or best_length is None:
        return None, None
    return f"{room.id}:{best_index}", round(best_length, 6)


def _opening_overlap(opening_points: list[tuple[float, float]], boundary: LineString) -> float:
    line = LineString(opening_points)
    if line.is_empty:
        return 0.0
    if not boundary.intersects(line):
        return 0.0

    intersection = line.intersection(boundary)
    if intersection.is_empty:
        return 0.0
    if intersection.geom_type == "Point":
        return 0.0

    return round(float(intersection.length), 6)


def _open_boundary_length(
    project: ProjectInput, room: RoomBoundary
) -> tuple[float, list[QuantityException]]:
    polygon = _room_polygon(room)
    boundary = polygon.boundary
    total = 0.0
    exceptions: list[QuantityException] = []

    for opening in project.openings:
        if opening.layer != LayerName.QUOTE_OPENING:
            continue
        opening_points = [(point.x, point.y) for point in opening.points]
        if not boundary.intersects(LineString(opening_points)):
            continue

        if not _floor_compatible(room.floor, opening.floor):
            exceptions.append(
                QuantityException(
                    code="marker_floor_mismatch_opening",
                    message=(
                        "marker_floor_mismatch_opening: "
                        f"Opening {opening.id} skipped for room {room.id} due floor mismatch"
                    ),
                    room_id=room.id,
                )
            )
            continue

        total += _opening_overlap(opening_points, boundary)

    return round(max(total, 0.0), 6), exceptions


def _wall_backed_boundary_length(project: ProjectInput, room: RoomBoundary) -> float | None:
    wall_segments = [
        (start, end)
        for wall in project.walls
        if wall.layer == LayerName.QUOTE_WALL and _floor_compatible(room.floor, wall.floor)
        for start, end in zip(wall.points, wall.points[1:])
    ]
    if not wall_segments:
        return None

    total = 0.0
    for boundary_start, boundary_end in zip(room.points, room.points[1:]):
        boundary_dx = boundary_end.x - boundary_start.x
        boundary_dy = boundary_end.y - boundary_start.y
        boundary_length = hypot(boundary_dx, boundary_dy)
        if boundary_length == 0:
            continue

        unit_x = boundary_dx / boundary_length
        unit_y = boundary_dy / boundary_length
        intervals: list[tuple[float, float]] = []

        for wall_start, wall_end in wall_segments:
            wall_dx = wall_end.x - wall_start.x
            wall_dy = wall_end.y - wall_start.y
            wall_length = hypot(wall_dx, wall_dy)
            if wall_length == 0:
                continue

            wall_unit_x = wall_dx / wall_length
            wall_unit_y = wall_dy / wall_length
            cross = abs(unit_x * wall_unit_y - unit_y * wall_unit_x)
            if cross > _WALL_PARALLEL_CROSS_TOLERANCE:
                continue

            boundary_line = LineString([(boundary_start.x, boundary_start.y), (boundary_end.x, boundary_end.y)])
            wall_line = LineString([(wall_start.x, wall_start.y), (wall_end.x, wall_end.y)])
            if boundary_line.distance(wall_line) > _WALL_BOUNDARY_TOLERANCE_METERS:
                continue

            start_projection = (wall_start.x - boundary_start.x) * unit_x + (wall_start.y - boundary_start.y) * unit_y
            end_projection = (wall_end.x - boundary_start.x) * unit_x + (wall_end.y - boundary_start.y) * unit_y
            interval_start = max(min(start_projection, end_projection), 0.0)
            interval_end = min(max(start_projection, end_projection), boundary_length)
            if interval_end > interval_start:
                intervals.append((interval_start, interval_end))

        total += _merged_interval_length(intervals)

    return round(max(total, 0.0), 6)


def _merged_interval_length(intervals: list[tuple[float, float]]) -> float:
    if not intervals:
        return 0.0

    sorted_intervals = sorted(intervals)
    merged: list[tuple[float, float]] = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))

    return sum(end - start for start, end in merged)


def _height_for_floor(project: ProjectInput, floor: str | None) -> float:
    if floor and floor in project.floor_heights:
        return project.floor_heights[floor]
    return project.default_height


def _polyline_points(marker) -> list[tuple[float, float]]:
    return [(point.x, point.y) for point in marker.points]


def _exterior_opening_length(project: ProjectInput, wall) -> float:
    wall_line = LineString(_polyline_points(wall))
    if wall_line.is_empty:
        return 0.0

    total = 0.0
    for opening in project.exterior_openings:
        if opening.layer != LayerName.QUOTE_EXT_OPENING:
            continue
        if not _floor_compatible(wall.floor, opening.floor):
            continue
        total += _opening_overlap(_polyline_points(opening), wall_line)
    return round(max(total, 0.0), 6)


def _calculate_exterior_rows(project: ProjectInput) -> list[ExteriorQuantityRow]:
    rows: list[ExteriorQuantityRow] = []
    for wall in project.exterior_walls:
        if wall.layer != LayerName.QUOTE_EXT_WALL:
            continue
        measure_length = round(LineString(_polyline_points(wall)).length, 6)
        height = _height_for_floor(project, wall.floor)
        opening_length = min(_exterior_opening_length(project, wall), measure_length)
        gross_area = round(measure_length * height, 6)
        net_area = round((measure_length - opening_length) * height, 6)
        rows.append(
            ExteriorQuantityRow(
                exterior_wall_id=wall.id,
                floor=wall.floor,
                height=height,
                measure_length=measure_length,
                opening_length=opening_length,
                gross_area=gross_area,
                net_area=net_area,
                include_in_quote=_quote_include_flag(wall.attributes.get("include_in_quote", True)),
            )
        )
    return rows


def _closed_marker_area(marker) -> float | None:
    points = marker.points
    if len(points) < 4:
        return None
    if points[0].x != points[-1].x or points[0].y != points[-1].y:
        return None
    try:
        area = closed_polygon_area(points)
    except ValueError:
        return None
    if area <= 0:
        return None
    return area


def _calculate_building_area(project: ProjectInput) -> float | None:
    exterior_areas = [
        area
        for marker in project.exterior_walls
        if marker.layer == LayerName.QUOTE_EXT_WALL
        for area in [_closed_marker_area(marker)]
        if area is not None
    ]
    if exterior_areas:
        return round(sum(exterior_areas), 6)

    building_areas = [
        area
        for marker in project.building_areas
        if marker.layer == LayerName.QUOTE_BUILDING_AREA
        for area in [_closed_marker_area(marker)]
        if area is not None
    ]
    if building_areas:
        return round(sum(building_areas), 6)
    return None


def _construction_detail_for_linear_marker(
    project: ProjectInput,
    marker: ConstructionMarker,
) -> ConstructionQuantityDetail:
    length = _polyline_marker_length(marker)
    effective_height, height_defaulted = _construction_effective_height(project, marker)
    area = length * effective_height if effective_height is not None else 0.0
    return ConstructionQuantityDetail(
        id=marker.id,
        kind=marker.kind,
        floor=marker.floor,
        length=round(length, 6),
        height=round(marker.height, 6) if marker.height is not None else None,
        effective_height=round(effective_height, 6) if effective_height is not None else None,
        height_defaulted=height_defaulted,
        thickness=round(marker.thickness, 6) if marker.thickness is not None else None,
        area=round(area, 6),
        count=1,
    )


def _construction_detail_for_count_marker(marker: ConstructionMarker) -> ConstructionQuantityDetail:
    return ConstructionQuantityDetail(
        id=marker.id,
        kind=marker.kind,
        floor=marker.floor,
        length=round(_polyline_marker_length(marker), 6),
        height=round(marker.height, 6) if marker.height is not None else None,
        thickness=round(marker.thickness, 6) if marker.thickness is not None else None,
        count=1,
    )


def _calculate_construction_details(project: ProjectInput) -> list[ConstructionQuantityDetail]:
    details: list[ConstructionQuantityDetail] = []
    details.extend(_construction_detail_for_linear_marker(project, marker) for marker in project.demo_walls)
    details.extend(_construction_detail_for_linear_marker(project, marker) for marker in project.new_walls)
    details.extend(_construction_detail_for_count_marker(marker) for marker in project.lintels)
    details.extend(_construction_detail_for_count_marker(marker) for marker in project.lintel_holes)
    return details


def _determine_status(exceptions: list[QuantityException], default_inferred: bool) -> DataStatus:
    for exc in exceptions:
        if exc.code in {
            "room_has_no_name",
            "ambiguous_room_text",
            "marker_floor_mismatch_text",
            "marker_floor_mismatch_window",
            "marker_floor_mismatch_door",
            "marker_floor_mismatch_opening",
            "marker_floor_mismatch_height",
            "marker_floor_mismatch_fixture",
            "ambiguous_window_assignment",
            "ambiguous_door_assignment",
            "ambiguous_height_assignment",
            "ambiguous_void_marker",
            "void_related_floor_height_missing",
            "window_area_exceeds_wall_area",
            "stair_special_quantity_manual",
            "fixture_marker_outside_assignment_tolerance",
            "fixture_marker_unmatched",
            "fixture_marker_in_excluded_room",
        }:
            return DataStatus.NEEDS_REVIEW
    if default_inferred:
        return DataStatus.DEFAULT_INFERRED
    return DataStatus.CONFIRMED


def calculate_quantities(project: ProjectInput) -> QuantityResult:
    rows: list[QuantityRow] = []
    building_area = _calculate_building_area(project)
    exterior_rows = _calculate_exterior_rows(project)
    construction_details = _calculate_construction_details(project)
    exceptions: list[QuantityException] = []

    room_name_assignments, name_exceptions = _resolve_room_names(project, project.rooms)
    exceptions.extend(name_exceptions)
    resolved_room_names = {
        room.id: room.name or room_name_assignments.get(room.id, "\u672a\u547d\u540d\u7a7a\u95f4")
        for room in project.rooms
    }

    void_height_assignments, void_height_exceptions = _resolve_void_height_assignments(project, project.rooms)
    exceptions.extend(void_height_exceptions)

    height_assignments, height_exceptions = _resolve_height_assignments(project, project.rooms)
    exceptions.extend(height_exceptions)

    window_assignments, window_exceptions = _resolve_window_assignments(project, project.rooms)
    exceptions.extend(window_exceptions)

    door_assignments, door_exceptions = _resolve_door_assignments(project, project.rooms)
    exceptions.extend(door_exceptions)

    custom_assignments, custom_exceptions = _resolve_fixture_assignments(
        project.rooms,
        project.custom_items,
        resolved_room_names,
    )
    exceptions.extend(custom_exceptions)
    cabinet_assignments, cabinet_exceptions = _resolve_fixture_assignments(
        project.rooms,
        project.cabinet_items,
        resolved_room_names,
    )
    exceptions.extend(cabinet_exceptions)

    for room in project.rooms:
        room_exceptions: list[QuantityException] = [
            exception for exception in exceptions if exception.room_id == room.id
        ]

        if room.name:
            room_name = room.name
        else:
            room_name = room_name_assignments.get(room.id, "未命名空间")
            if room.id not in room_name_assignments and not any(
                exception.code == "room_has_no_name" for exception in room_exceptions
            ):
                missing_name_exception = QuantityException(
                    code="room_has_no_name",
                    message=f"Room {room.id} has no name",
                    room_id=room.id,
                )
                room_exceptions.append(missing_name_exception)
                exceptions.append(missing_name_exception)

        if room.attributes.get("height") is not None:
            height = float(room.attributes["height"])
            height_mode = HeightMode.MANUAL
        elif room.space_type is SpaceType.VOID and room.id in void_height_assignments:
            height, height_mode = void_height_assignments[room.id]
        elif room.id in height_assignments:
            height, height_mode = height_assignments[room.id]
        elif room.floor and room.floor in project.floor_heights:
            height = project.floor_heights[room.floor]
            height_mode = HeightMode.FLOOR_DEFAULT
        else:
            height = project.default_height
            height_mode = HeightMode.PROJECT_DEFAULT

        floor_area = closed_polygon_area(room.points)
        floor_perimeter = closed_polygon_perimeter(room.points)
        open_boundary_length, open_boundary_exceptions = _open_boundary_length(project, room)
        if open_boundary_exceptions:
            room_exceptions.extend(open_boundary_exceptions)
            exceptions.extend(open_boundary_exceptions)
        wall_backed_boundary_length = _wall_backed_boundary_length(project, room)
        if wall_backed_boundary_length is None:
            wall_measure_perimeter = max(floor_perimeter - open_boundary_length, 0.0)
        else:
            wall_measure_perimeter = max(wall_backed_boundary_length - open_boundary_length, 0.0)
            open_boundary_length = round(max(floor_perimeter - wall_measure_perimeter, 0.0), 6)

        room_windows = window_assignments.get(room.id, [])
        window_count = len(room_windows)
        window_area = 0.0
        window_details: list[WindowQuantityDetail] = []
        has_defaulted_window_height = False
        for window in room_windows:
            if window.height is None:
                has_defaulted_window_height = True
                height_value = project.default_window_height
                height_defaulted = True
            else:
                height_value = window.height
                height_defaulted = False
            detail_area = window.width * height_value
            window_area += detail_area
            wall_segment_key, wall_segment_length = _nearest_room_segment_detail(window.point, room)
            window_details.append(
                WindowQuantityDetail(
                    id=window.id,
                    width=round(window.width, 6),
                    height=round(height_value, 6),
                    area=round(detail_area, 6),
                    height_defaulted=height_defaulted,
                    wall_segment_key=wall_segment_key,
                    wall_segment_length=wall_segment_length,
                )
            )

            if window.height is None:
                room_exceptions.append(
                    QuantityException(
                        code="window_height_defaulted",
                        message=f"Window {window.id} used default height {height_value}",
                        room_id=room.id,
                    )
                )
                exceptions.append(room_exceptions[-1])

        gross_wall_area = round(wall_measure_perimeter * height, 6)
        if window_area > gross_wall_area:
            net_wall_area = 0.0
            exception = QuantityException(
                code="window_area_exceeds_wall_area",
                message=(
                    "window_area_exceeds_wall_area: "
                    f"Window area {round(window_area, 6)} exceeds gross wall area {gross_wall_area} "
                    f"for room {room.id}"
                ),
                room_id=room.id,
            )
            room_exceptions.append(exception)
            exceptions.append(exception)
        else:
            net_wall_area = round(gross_wall_area - window_area, 6)

        room_doors = door_assignments.get(room.id, [])
        door_opening_count = len(room_doors)
        door_opening_area = 0.0
        door_details: list[DoorQuantityDetail] = []
        for door in room_doors:
            if door.width is not None and door.height is not None:
                door_opening_area += door.width * door.height
            effective_height = door.height if door.height is not None else _DEFAULT_DOOR_DETAIL_HEIGHT_METERS
            height_defaulted = door.height is None and door.width is not None
            detail_area = door.width * effective_height if door.width is not None else 0.0
            door_details.append(
                DoorQuantityDetail(
                    id=door.id,
                    room_id=room.id,
                    width=round(door.width, 6) if door.width is not None else None,
                    height=round(door.height, 6) if door.height is not None else None,
                    effective_height=round(effective_height, 6) if door.width is not None else None,
                    height_defaulted=height_defaulted,
                    area=round(detail_area, 6),
                )
            )

        if room.space_type is SpaceType.STAIR:
            exception = QuantityException(
                code="stair_special_quantity_manual",
                message=(
                    "stair_special_quantity_manual: "
                    f"Room {room.id} requires manual stair-specific quantities"
                ),
                room_id=room.id,
            )
            room_exceptions.append(exception)
            exceptions.append(exception)

        status = _determine_status(room_exceptions, has_defaulted_window_height)
        custom_details = _custom_details_for_room(
            room,
            room_name,
            custom_assignments.get(room.id, []),
        )
        cabinet_details = _cabinet_details_for_room(
            room,
            room_name,
            cabinet_assignments.get(room.id, []),
        )

        is_excluded_area_space = _is_excluded_area_space(room)
        if is_excluded_area_space:
            status = DataStatus.EXCLUDED
            floor_area = 0.0
            floor_perimeter = 0.0  # used for completeness
            open_boundary_length = 0.0
            wall_measure_perimeter = 0.0
            gross_wall_area = 0.0
            window_count = 0
            window_area = 0.0
            window_details = []
            door_opening_count = 0
            door_opening_area = 0.0
            door_details = []
            custom_details = []
            cabinet_details = []
            net_wall_area = 0.0

            include_in_floor_quantity = False
            include_in_wall_paint_quantity = False
        else:
            include_in_floor_quantity = room.include_in_floor_quantity
            include_in_wall_paint_quantity = room.include_in_wall_paint_quantity

        rows.append(
            QuantityRow(
                room_id=room.id,
                floor=room.floor,
                room_name=room_name,
                space_type=room.space_type,
                height=height,
                height_mode=height_mode,
                floor_area=round(floor_area, 6),
                floor_perimeter=round(floor_perimeter, 6),
                wall_measure_perimeter=round(wall_measure_perimeter, 6),
                open_boundary_length=open_boundary_length,
                gross_wall_area=gross_wall_area,
                window_count=window_count,
                window_area=round(window_area, 6),
                window_details=window_details,
                door_opening_count=door_opening_count,
                door_opening_area=round(door_opening_area, 6),
                door_details=door_details,
                custom_details=custom_details,
                cabinet_details=cabinet_details,
                net_wall_area=net_wall_area,
                is_outdoor=room.is_outdoor,
                include_in_floor_quantity=include_in_floor_quantity,
                include_in_wall_paint_quantity=include_in_wall_paint_quantity,
                status=status,
                exception_notes=[exception.message for exception in room_exceptions],
            )
        )

    return QuantityResult(
        project_name=project.project_name,
        rows=rows,
        building_area=building_area,
        exterior_rows=exterior_rows,
        construction_details=construction_details,
        exceptions=exceptions,
    )
