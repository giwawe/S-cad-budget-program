from __future__ import annotations

from math import isclose
from shapely.geometry import LineString, Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.geometry import closed_polygon_area, closed_polygon_perimeter, point_inside_polygon
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


def _room_polygon(room: RoomBoundary) -> Polygon:
    return Polygon((point.x, point.y) for point in room.points)


def _room_name(project: ProjectInput, room: RoomBoundary) -> tuple[str, list[QuantityException]]:
    if room.name:
        return room.name, []

    names = [text.text for text in project.texts if point_inside_polygon(text.point, room.points)]
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
        QuantityException(
            code="room_has_no_name",
            message=f"Room {room.id} has no name",
            room_id=room.id,
        )
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


def _opening_boundary_overlap(opening_line: list[ShapelyPoint], boundary: LineString) -> float:
    line = LineString(opening_line)
    if line.is_empty:
        return 0.0
    if line.is_simple is False and line.length < 0:
        return 0.0
    intersection = line.intersection(boundary)
    if intersection.is_empty:
        return 0.0

    # If the opening lies across the room edge, count only the overlapping part.
    overlap_length = intersection.length
    if not overlap_length and hasattr(intersection, "geom_type") and intersection.geom_type == "Point":
        return 0.0
    return round(float(overlap_length), 6)


def _open_boundary_length(project: ProjectInput, room: RoomBoundary) -> float:
    polygon = _room_polygon(room)
    boundary = polygon.boundary

    total = 0.0
    for opening in project.openings:
        if opening.layer.name != "QUOTE_OPENING":
            continue

        line = LineString((point.x, point.y) for point in opening.points)
        if not line.is_empty and boundary.distance(line) <= 0:
            total += _opening_boundary_overlap([(point.x, point.y) for point in opening.points], boundary)
        elif not line.is_empty and boundary.intersects(line):
            # Keep legacy behavior tolerant: any intersection at least touches boundary.
            total += _opening_boundary_overlap([(point.x, point.y) for point in opening.points], boundary)

    return round(max(total, 0.0), 6)


def _window_area(project: ProjectInput, room: RoomBoundary) -> tuple[int, float, list[QuantityException], DataStatus]:
    count = 0
    area = 0.0
    status = DataStatus.CONFIRMED
    exceptions: list[QuantityException] = []

    for window in project.windows:
        if not point_inside_polygon(window.point, room.points):
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


def _merge_status(*statuses: DataStatus) -> DataStatus:
    if DataStatus.NEEDS_REVIEW in statuses:
        return DataStatus.NEEDS_REVIEW
    if DataStatus.DEFAULT_INFERRED in statuses:
        return DataStatus.DEFAULT_INFERRED
    return DataStatus.CONFIRMED


def calculate_quantities(project: ProjectInput) -> QuantityResult:
    rows: list[QuantityRow] = []
    exceptions: list[QuantityException] = []

    for room in project.rooms:
        room_exceptions: list[QuantityException] = []

        room_name, name_exceptions = _room_name(project, room)
        room_exceptions.extend(name_exceptions)

        height, height_mode = _height(project, room)

        floor_area = closed_polygon_area(room.points)
        floor_perimeter = closed_polygon_perimeter(room.points)
        open_boundary_length = _open_boundary_length(project, room)
        wall_measure_perimeter = max(floor_perimeter - open_boundary_length, 0.0)
        if isclose(wall_measure_perimeter, 0.0, abs_tol=1e-12):
            wall_measure_perimeter = 0.0
        wall_measure_perimeter = round(wall_measure_perimeter, 6)

        window_count, window_area, window_exceptions, window_status = _window_area(project, room)
        room_exceptions.extend(window_exceptions)

        gross_wall_area = round(wall_measure_perimeter * height, 6)
        net_wall_area = round(gross_wall_area - window_area, 6)

        row_status = _merge_status(
            DataStatus.CONFIRMED,
            DataStatus.DEFAULT_INFERRED if room_exceptions else DataStatus.CONFIRMED,
        )
        if window_status is DataStatus.DEFAULT_INFERRED:
            row_status = DataStatus.DEFAULT_INFERRED
        if any(exc.code == "multiple_room_names" for exc in room_exceptions) or any(
            exc.code == "room_has_no_name" for exc in room_exceptions
        ):
            row_status = DataStatus.NEEDS_REVIEW

        if room.space_type is SpaceType.ELEVATOR_SHAFT:
            row_status = DataStatus.EXCLUDED
            floor_area = 0.0
            floor_perimeter = 0.0
            open_boundary_length = 0.0
            wall_measure_perimeter = 0.0
            gross_wall_area = 0.0
            net_wall_area = 0.0

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
                wall_measure_perimeter=wall_measure_perimeter,
                open_boundary_length=open_boundary_length,
                gross_wall_area=gross_wall_area,
                window_count=window_count,
                window_area=window_area,
                door_opening_count=0,
                door_opening_area=0.0,
                net_wall_area=net_wall_area,
                is_outdoor=room.is_outdoor,
                include_in_floor_quantity=room.include_in_floor_quantity,
                include_in_wall_paint_quantity=room.include_in_wall_paint_quantity,
                status=row_status,
                exception_notes=[exception.message for exception in room_exceptions],
            )
        )
        exceptions.extend(room_exceptions)

    return QuantityResult(project_name=project.project_name, rows=rows, exceptions=exceptions)
