from collections.abc import Iterable
from math import ceil, cos, hypot, pi, sin

import ezdxf
from ezdxf.math import Vec2, bulge_to_arc
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.cad_adapter_models import (
    AdapterIssue,
    AdapterSeverity,
    CadImportOptions,
    CadImportResult,
    CadUnit,
)
from cad_budget.models import (
    DoorMarker,
    HeightMarker,
    LayerName,
    Point,
    PolylineMarker,
    ProjectInput,
    RoomBoundary,
    TextMarker,
    VoidMarker,
    WindowMarker,
)


_UNIT_SCALE_TO_METERS = {
    CadUnit.MILLIMETER: 0.001,
    CadUnit.CENTIMETER: 0.01,
    CadUnit.METER: 1.0,
}

_DXF_INSUNITS = {
    4: CadUnit.MILLIMETER,
    5: CadUnit.CENTIMETER,
    6: CadUnit.METER,
}

_ROOM_CLOSURE_TOLERANCE_METERS = 0.001


def _scale(value: float, unit: CadUnit) -> float:
    return value * _UNIT_SCALE_TO_METERS[unit]


def _entity_id(entity) -> str:
    return str(entity.dxf.handle)


def _layer(entity) -> str:
    return str(entity.dxf.layer).upper()


def _point(x: float, y: float, unit: CadUnit) -> Point:
    return Point(x=_scale(float(x), unit), y=_scale(float(y), unit))


def _arc_points_from_bulge(
    start: tuple[float, float], end: tuple[float, float], bulge: float, unit: CadUnit
) -> list[Point]:
    center, start_angle, end_angle, radius = bulge_to_arc(Vec2(start), Vec2(end), bulge)
    angle_span = end_angle - start_angle
    if bulge < 0 and angle_span > 0:
        angle_span -= 2 * pi
    if bulge > 0 and angle_span < 0:
        angle_span += 2 * pi

    segment_count = max(4, ceil(abs(angle_span) / (pi / 12)))
    points: list[Point] = []
    for index in range(1, segment_count + 1):
        angle = start_angle + angle_span * index / segment_count
        points.append(_point(center.x + radius * cos(angle), center.y + radius * sin(angle), unit))
    return points


def _segment_points(
    start: tuple[float, float], end: tuple[float, float], bulge: float, unit: CadUnit
) -> list[Point]:
    if bulge:
        return _arc_points_from_bulge(start, end, bulge, unit)
    return [_point(end[0], end[1], unit)]


def _lwpolyline_points(entity, unit: CadUnit) -> list[Point]:
    raw_vertices = list(entity.get_points("xyb"))
    if not raw_vertices:
        return []

    points = [_point(raw_vertices[0][0], raw_vertices[0][1], unit)]
    for current, following in zip(raw_vertices, raw_vertices[1:]):
        start = (current[0], current[1])
        end = (following[0], following[1])
        points.extend(_segment_points(start, end, float(current[2] or 0), unit))

    if entity.closed:
        last = raw_vertices[-1]
        first = raw_vertices[0]
        start = (last[0], last[1])
        end = (first[0], first[1])
        if start != end:
            points.extend(_segment_points(start, end, float(last[2] or 0), unit))

    if entity.closed and points and (points[0].x != points[-1].x or points[0].y != points[-1].y):
        points.append(points[0])
    return points


def _polyline_length(points: list[Point]) -> float:
    return round(
        sum(
            hypot(following.x - current.x, following.y - current.y)
            for current, following in zip(points, points[1:])
        ),
        10,
    )


def _outline_centroid(points: list[Point]) -> Point:
    centroid = Polygon((point.x, point.y) for point in points).centroid
    return Point(x=centroid.x, y=centroid.y)


def _outline_width(polygon: Polygon) -> float:
    rectangle = polygon.minimum_rotated_rectangle
    if not hasattr(rectangle, "exterior"):
        return 0.0
    rectangle_points = list(rectangle.exterior.coords)
    return round(
        max(
            hypot(following[0] - current[0], following[1] - current[1])
            for current, following in zip(rectangle_points, rectangle_points[1:])
        ),
        10,
    )


def _outline_polygon(points: list[Point]) -> Polygon | None:
    polygon = Polygon((point.x, point.y) for point in points)
    if polygon.is_empty or polygon.area <= 0:
        return None
    return polygon


def _valid_room_polygon(points: list[Point]) -> bool:
    try:
        polygon = Polygon((point.x, point.y) for point in points)
    except ValueError:
        return False
    return not polygon.is_empty and polygon.area > 0 and polygon.is_valid


def _points_within_tolerance(first: Point, second: Point, tolerance: float) -> bool:
    return hypot(second.x - first.x, second.y - first.y) <= tolerance


def _room_boundary_can_be_closed(points: list[Point]) -> bool:
    if len(points) < 4:
        return False
    return _points_within_tolerance(points[0], points[-1], _ROOM_CLOSURE_TOLERANCE_METERS)


def _snap_room_boundary_closed(points: list[Point]) -> list[Point]:
    if points and _room_boundary_can_be_closed(points):
        points[-1] = points[0]
    return points


def _line_midpoint(points: list[Point]) -> Point:
    first = points[0]
    last = points[-1]
    return Point(x=(first.x + last.x) / 2, y=(first.y + last.y) / 2)


def _file_unit_issue(doc, options: CadImportOptions) -> AdapterIssue | None:
    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    file_unit = _DXF_INSUNITS.get(insunits)
    if file_unit is None:
        return AdapterIssue(
            code="CAD_UNIT_UNCONFIRMED",
            message="DXF unit is missing or unsupported; using user-confirmed unit.",
        )
    if file_unit != options.confirmed_unit:
        return AdapterIssue(
            code="CAD_UNIT_CONFLICT",
            message=f"DXF unit is {file_unit.value}, but user confirmed {options.confirmed_unit.value}.",
            severity=AdapterSeverity.BLOCKER,
        )
    return None


def _text_point(entity, unit: CadUnit) -> Point:
    insert = entity.dxf.insert
    return _point(insert.x, insert.y, unit)


def _line_points(entity, unit: CadUnit) -> list[Point]:
    start = entity.dxf.start
    end = entity.dxf.end
    return [_point(start.x, start.y, unit), _point(end.x, end.y, unit)]


def _insert_point(entity, unit: CadUnit) -> Point:
    insert = entity.dxf.insert
    return _point(insert.x, insert.y, unit)


def _insert_width(entity, unit: CadUnit) -> float | None:
    width = max(abs(float(entity.dxf.xscale)), abs(float(entity.dxf.yscale)))
    if width <= 0:
        return None
    return _scale(width, unit)


def _text_value(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return str(entity.dxf.text).strip()


def _parse_float_text(value: str) -> float | None:
    cleaned = value.strip()
    if cleaned.lower().endswith("m"):
        cleaned = cleaned[:-1].strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _polygon_from_room(room: RoomBoundary) -> Polygon:
    return Polygon((point.x, point.y) for point in room.points)


def _assign_text_names(rooms: list[RoomBoundary], texts: list[TextMarker]) -> None:
    for room in rooms:
        polygon = _polygon_from_room(room)
        matches = [text for text in texts if polygon.contains(ShapelyPoint(text.point.x, text.point.y))]
        if len(matches) == 1:
            room.name = matches[0].text


def _iter_modelspace(doc) -> Iterable:
    return doc.modelspace()


def import_dxf(options: CadImportOptions) -> CadImportResult:
    issues: list[AdapterIssue] = []
    try:
        doc = ezdxf.readfile(options.source_path)
    except (OSError, ezdxf.DXFError) as exc:
        return CadImportResult(
            source_path=options.source_path,
            dxf_path=options.source_path,
            issues=[
                AdapterIssue(
                    code="DXF_READ_FAILED",
                    message=f"Failed to read DXF: {exc}",
                    severity=AdapterSeverity.BLOCKER,
                )
            ],
        )

    rooms: list[RoomBoundary] = []
    texts: list[TextMarker] = []
    windows: list[WindowMarker] = []
    doors: list[DoorMarker] = []
    walls: list[PolylineMarker] = []
    openings: list[PolylineMarker] = []
    heights: list[HeightMarker] = []
    voids: list[VoidMarker] = []
    exterior_walls: list[PolylineMarker] = []
    exterior_openings: list[PolylineMarker] = []

    for entity in _iter_modelspace(doc):
        layer = _layer(entity)
        if layer == LayerName.QUOTE_ROOM.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if not entity.closed and not _room_boundary_can_be_closed(points):
                issues.append(
                    AdapterIssue(
                        code="ROOM_BOUNDARY_INVALID",
                        message="Room boundary must be closed or have endpoints within 1mm.",
                        severity=AdapterSeverity.BLOCKER,
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
                continue
            points = _snap_room_boundary_closed(points)
            if not _valid_room_polygon(points):
                issues.append(
                    AdapterIssue(
                        code="ROOM_BOUNDARY_INVALID",
                        message="Room boundary must be a valid closed polygon with positive area.",
                        severity=AdapterSeverity.BLOCKER,
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
                continue
            try:
                rooms.append(RoomBoundary(id=_entity_id(entity), points=points))
            except ValueError as exc:
                issues.append(
                    AdapterIssue(
                        code="ROOM_BOUNDARY_INVALID",
                        message=str(exc),
                        severity=AdapterSeverity.BLOCKER,
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
        elif layer == LayerName.QUOTE_TEXT.value and entity.dxftype() in {"TEXT", "MTEXT"}:
            value = _text_value(entity)
            if value:
                texts.append(TextMarker(id=_entity_id(entity), text=value, point=_text_point(entity, options.confirmed_unit)))
        elif layer == LayerName.QUOTE_HEIGHT.value and entity.dxftype() in {"TEXT", "MTEXT"}:
            value = _text_value(entity)
            height = _parse_float_text(value)
            if height is None:
                issues.append(
                    AdapterIssue(
                        code="HEIGHT_TEXT_INVALID",
                        message=f"Height text must be a numeric meter value: {value!r}.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
            else:
                heights.append(
                    HeightMarker(
                        id=_entity_id(entity),
                        point=_text_point(entity, options.confirmed_unit),
                        height=height,
                    )
                )
        elif layer == LayerName.QUOTE_WINDOW.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) < 4 and not entity.closed:
                continue
            if not entity.closed and not _room_boundary_can_be_closed(points):
                issues.append(
                    AdapterIssue(
                        code="WINDOW_OUTLINE_NOT_CLOSED",
                        message="Window outline must be a closed LWPOLYLINE with enough points.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
                continue
            points = _snap_room_boundary_closed(points)
            if len(points) < 4:
                issues.append(
                    AdapterIssue(
                        code="WINDOW_OUTLINE_NOT_CLOSED",
                        message="Window outline must be a closed LWPOLYLINE with enough points.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
            else:
                polygon = _outline_polygon(points)
                if polygon is None:
                    issues.append(
                        AdapterIssue(
                            code="WINDOW_OUTLINE_INVALID",
                            message="Window outline must enclose a non-zero area.",
                            entity_id=_entity_id(entity),
                            layer=layer,
                        )
                    )
                    continue
                windows.append(
                    WindowMarker(
                        id=_entity_id(entity),
                        point=_outline_centroid(points),
                        width=_outline_width(polygon),
                        height=None,
                        attributes={"source": "closed_outline"},
                    )
                )
        elif layer == LayerName.QUOTE_DOOR.value and entity.dxftype() == "INSERT":
            width = _insert_width(entity, options.confirmed_unit)
            if width is not None:
                doors.append(
                    DoorMarker(
                        id=_entity_id(entity),
                        point=_insert_point(entity, options.confirmed_unit),
                        width=width,
                        attributes={"source": "insert", "block_name": str(entity.dxf.name)},
                    )
                )
        elif layer == LayerName.QUOTE_DOOR.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                if entity.closed and len(points) >= 4:
                    polygon = _outline_polygon(points)
                    if polygon is None:
                        issues.append(
                            AdapterIssue(
                                code="DOOR_OUTLINE_INVALID",
                                message="Door outline must enclose a non-zero area.",
                                entity_id=_entity_id(entity),
                                layer=layer,
                            )
                        )
                        continue
                    point = _outline_centroid(points)
                    width = _outline_width(polygon)
                else:
                    point = _line_midpoint(points)
                    width = _polyline_length(points)
                doors.append(
                    DoorMarker(
                        id=_entity_id(entity),
                        point=point,
                        width=width,
                        attributes={"source": "geometry"},
                    )
                )
        elif layer == LayerName.QUOTE_WALL.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                walls.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_WALL, points=points))
        elif layer == LayerName.QUOTE_WALL.value and entity.dxftype() == "LINE":
            walls.append(
                PolylineMarker(
                    id=_entity_id(entity),
                    layer=LayerName.QUOTE_WALL,
                    points=_line_points(entity, options.confirmed_unit),
                )
            )
        elif layer == LayerName.QUOTE_OPENING.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                openings.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_OPENING, points=points))
        elif layer == LayerName.QUOTE_VOID.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if points:
                voids.append(VoidMarker(id=_entity_id(entity), points=points))
        elif layer == LayerName.QUOTE_EXT_WALL.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                exterior_walls.append(PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_EXT_WALL, points=points))
        elif layer == LayerName.QUOTE_EXT_OPENING.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                exterior_openings.append(
                    PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_EXT_OPENING, points=points)
                )

    if not rooms:
        issues.append(
            AdapterIssue(
                code="QUOTE_ROOM_MISSING",
                message="DXF does not contain any closed room boundary on QUOTE_ROOM.",
                severity=AdapterSeverity.BLOCKER,
                layer=LayerName.QUOTE_ROOM.value,
            )
        )

    unit_issue = _file_unit_issue(doc, options)
    if unit_issue is not None:
        issues.append(unit_issue)

    _assign_text_names(rooms, texts)
    project = ProjectInput(
        project_name=options.project_name,
        default_height=options.default_height,
        default_window_height=options.default_window_height,
        floor_heights=options.floor_heights,
        rooms=rooms,
        texts=texts,
        windows=windows,
        doors=doors,
        walls=walls,
        openings=openings,
        heights=heights,
        voids=voids,
        exterior_walls=exterior_walls,
        exterior_openings=exterior_openings,
    )
    return CadImportResult(project=project, issues=issues, source_path=options.source_path, dxf_path=options.source_path)
