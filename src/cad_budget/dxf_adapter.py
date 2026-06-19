from collections.abc import Iterable
from math import ceil, cos, pi, sin

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
from cad_budget.models import LayerName, Point, ProjectInput, RoomBoundary, TextMarker


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

    if points and (points[0].x != points[-1].x or points[0].y != points[-1].y):
        points.append(points[0])
    return points


def _max_room_dimension(doc) -> float | None:
    max_dimension: float | None = None
    for entity in _iter_modelspace(doc):
        if _layer(entity) != LayerName.QUOTE_ROOM.value or entity.dxftype() != "LWPOLYLINE" or not entity.closed:
            continue
        vertices = list(entity.get_points("xy"))
        if not vertices:
            continue
        xs = [float(vertex[0]) for vertex in vertices]
        ys = [float(vertex[1]) for vertex in vertices]
        dimension = max(max(xs) - min(xs), max(ys) - min(ys))
        max_dimension = dimension if max_dimension is None else max(max_dimension, dimension)
    return max_dimension


def _looks_like_default_meter_header(file_unit: CadUnit, confirmed_unit: CadUnit, max_dimension: float | None) -> bool:
    return (
        file_unit == CadUnit.METER
        and confirmed_unit in {CadUnit.MILLIMETER, CadUnit.CENTIMETER}
        and max_dimension is not None
        and max_dimension > 100
    )


def _file_unit_issue(doc, options: CadImportOptions) -> AdapterIssue | None:
    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    file_unit = _DXF_INSUNITS.get(insunits)
    if file_unit is None:
        return AdapterIssue(
            code="CAD_UNIT_UNCONFIRMED",
            message="DXF unit is missing or unsupported; using user-confirmed unit.",
        )
    if file_unit != options.confirmed_unit:
        if _looks_like_default_meter_header(file_unit, options.confirmed_unit, _max_room_dimension(doc)):
            return AdapterIssue(
                code="CAD_UNIT_UNCONFIRMED",
                message="DXF unit appears to be an unconfirmed default; using user-confirmed unit.",
            )
        return AdapterIssue(
            code="CAD_UNIT_CONFLICT",
            message=f"DXF unit is {file_unit.value}, but user confirmed {options.confirmed_unit.value}.",
            severity=AdapterSeverity.BLOCKER,
        )
    return None


def _text_point(entity, unit: CadUnit) -> Point:
    insert = entity.dxf.insert
    return _point(insert.x, insert.y, unit)


def _text_value(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return str(entity.dxf.text).strip()


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

    for entity in _iter_modelspace(doc):
        layer = _layer(entity)
        if layer == LayerName.QUOTE_ROOM.value and entity.dxftype() == "LWPOLYLINE" and entity.closed:
            points = _lwpolyline_points(entity, options.confirmed_unit)
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
    )
    return CadImportResult(project=project, issues=issues, source_path=options.source_path, dxf_path=options.source_path)
