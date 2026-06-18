from __future__ import annotations

from collections import defaultdict
from typing import Any

from shapely.geometry import LineString, Polygon

from cad_budget.geometry import closed_polygon_area, closed_polygon_perimeter, point_inside_polygon
from cad_budget.models import VoidMarker
from cad_budget.models import (
    DataStatus,
    HeightMode,
    LayerName,
    ProjectInput,
    QuantityException,
    QuantityResult,
    QuantityRow,
    RoomBoundary,
    SpaceType,
)


def _floor_compatible(room_floor: str | None, marker_floor: str | None) -> bool:
    return room_floor == marker_floor


def _resolve_room_names(project: ProjectInput, rooms: list[RoomBoundary]) -> tuple[dict[str, str], list[QuantityException]]:
    assignments: dict[str, str] = {}
    exceptions: list[QuantityException] = []
    matched_names: dict[str, list[str]] = defaultdict(list)

    for text in project.texts:
        matched_room_ids = [
            room.id
            for room in rooms
            if not room.name
            and _floor_compatible(room.floor, text.floor)
            and point_inside_polygon(text.point, room.points)
        ]
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

    explicit_by_room: dict[str, list[float]] = defaultdict(list)
    point_candidates: dict[str, list[tuple[float, str]]] = defaultdict(list)

    for marker in project.heights:
        if marker.room_id:
            for room in rooms:
                if room.id != marker.room_id:
                    continue
                if marker.floor is not None and room.floor != marker.floor:
                    continue
                explicit_by_room[room.id].append(marker.height)
            continue

        candidate_rooms = [
            room.id
            for room in rooms
            if _floor_compatible(room.floor, marker.floor) and point_inside_polygon(marker.point, room.points)
        ]
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
            if heights:
                assigned[room.id] = (heights[0], HeightMode.QUOTE_HEIGHT)
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
        matched_room_ids = [
            room.id
            for room in rooms
            if _floor_compatible(room.floor, window.floor) and point_inside_polygon(window.point, room.points)
        ]
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


def _open_boundary_length(project: ProjectInput, room: RoomBoundary) -> float:
    polygon = _room_polygon(room)
    boundary = polygon.boundary
    total = 0.0

    for opening in project.openings:
        if opening.layer != LayerName.QUOTE_OPENING:
            continue
        if not _floor_compatible(room.floor, opening.floor):
            continue

        total += _opening_overlap([(point.x, point.y) for point in opening.points], boundary)

    return round(max(total, 0.0), 6)


def _determine_status(exceptions: list[QuantityException], default_inferred: bool) -> DataStatus:
    for exc in exceptions:
        if exc.code in {
            "room_has_no_name",
            "ambiguous_room_text",
            "ambiguous_window_assignment",
            "ambiguous_height_assignment",
            "ambiguous_void_marker",
            "void_related_floor_height_missing",
        }:
            return DataStatus.NEEDS_REVIEW
    if default_inferred:
        return DataStatus.DEFAULT_INFERRED
    return DataStatus.CONFIRMED


def calculate_quantities(project: ProjectInput) -> QuantityResult:
    rows: list[QuantityRow] = []
    exceptions: list[QuantityException] = []

    room_name_assignments, name_exceptions = _resolve_room_names(project, project.rooms)
    exceptions.extend(name_exceptions)

    void_height_assignments, void_height_exceptions = _resolve_void_height_assignments(project, project.rooms)
    exceptions.extend(void_height_exceptions)

    height_assignments, height_exceptions = _resolve_height_assignments(project, project.rooms)
    exceptions.extend(height_exceptions)

    window_assignments, window_exceptions = _resolve_window_assignments(project, project.rooms)
    exceptions.extend(window_exceptions)

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
        open_boundary_length = _open_boundary_length(project, room)
        wall_measure_perimeter = max(floor_perimeter - open_boundary_length, 0.0)

        room_windows = window_assignments.get(room.id, [])
        window_count = len(room_windows)
        window_area = 0.0
        has_defaulted_window_height = False
        for window in room_windows:
            if window.height is None:
                has_defaulted_window_height = True
                height_value = project.default_window_height
            else:
                height_value = window.height
            window_area += window.width * height_value

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
        net_wall_area = round(gross_wall_area - window_area, 6)

        status = _determine_status(room_exceptions, has_defaulted_window_height)

        is_excluded_area_space = room.space_type in {SpaceType.ELEVATOR_SHAFT, SpaceType.VOID_OPENING}
        if is_excluded_area_space:
            status = DataStatus.EXCLUDED
            floor_area = 0.0
            floor_perimeter = 0.0  # used for completeness
            open_boundary_length = 0.0
            wall_measure_perimeter = 0.0
            gross_wall_area = 0.0
            window_count = 0
            window_area = 0.0
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
                door_opening_count=0,
                door_opening_area=0.0,
                net_wall_area=net_wall_area,
                is_outdoor=room.is_outdoor,
                include_in_floor_quantity=include_in_floor_quantity,
                include_in_wall_paint_quantity=include_in_wall_paint_quantity,
                status=status,
                exception_notes=[exception.message for exception in room_exceptions],
            )
        )

    return QuantityResult(project_name=project.project_name, rows=rows, exceptions=exceptions)
