from collections.abc import Iterable
from math import ceil, cos, hypot, pi, sin

import ezdxf
from ezdxf.math import Vec2, bulge_to_arc
from shapely.geometry import LineString, MultiPoint
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
    ConstructionKind,
    ConstructionMarker,
    DoorMarker,
    FixtureKind,
    FixtureMarker,
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
_FLOOR_POINT_MATCH_TOLERANCE_METERS = 0.3
_FLOOR_LINE_MATCH_TOLERANCE_METERS = 0.1
_WINDOW_WIDTH_ATTRIBUTE_KEYS = ("width", "窗宽", "宽")
_WINDOW_HEIGHT_ATTRIBUTE_KEYS = ("height", "窗高", "高")
_DOOR_WIDTH_ATTRIBUTE_KEYS = ("width", "门宽", "宽")
_DOOR_HEIGHT_ATTRIBUTE_KEYS = ("height", "门高", "高")
_FIXTURE_HEIGHT_ATTRIBUTE_KEYS = ("height", "HEIGHT", "高")
_FIXTURE_TYPE_ATTRIBUTE_KEYS = ("type", "TYPE", "类型")
_FIXTURE_ROOM_ATTRIBUTE_KEYS = ("room", "ROOM", "空间")
_FIXTURE_ROOM_ID_ATTRIBUTE_KEYS = ("room_id", "ROOM_ID")
_FIXTURE_XDATA_APPIDS = ("CAD_BUDGET",)
_CONSTRUCTION_HEIGHT_ATTRIBUTE_KEYS = ("height", "HEIGHT")
_CONSTRUCTION_THICKNESS_ATTRIBUTE_KEYS = ("thickness", "THICKNESS")


_QUOTE_LAYER_NAMES = {layer.value for layer in LayerName}


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


def _outline_width_from_points(points: list[Point]) -> float:
    hull = MultiPoint([(point.x, point.y) for point in points]).convex_hull
    rectangle = hull.minimum_rotated_rectangle
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


def _cabinet_footprint_length_from_points(points: list[Point]) -> float:
    polygon = _outline_polygon(points)
    if polygon is None:
        return 0.0
    segment_lengths = []
    for current, following in zip(points, points[1:]):
        segment_length = hypot(following.x - current.x, following.y - current.y)
        if segment_length > 0.05:
            segment_lengths.append(segment_length)
    if not segment_lengths:
        return 0.0
    depth = min(segment_lengths)
    if depth <= 0:
        return 0.0
    return round(polygon.area / depth, 10)


def _outline_polygon(points: list[Point]) -> Polygon | None:
    polygon = Polygon((point.x, point.y) for point in points)
    if polygon.is_empty or polygon.area <= 0:
        return None
    return polygon


def _fixture_marker_from_points(
    entity,
    points: list[Point],
    layer: LayerName,
    kind: FixtureKind,
    fixture_type_override: str | None = None,
) -> FixtureMarker | None:
    if len(points) < 2:
        return None
    if len(points) >= 4 and _points_within_tolerance(points[0], points[-1], 0.01):
        if kind is FixtureKind.CABINET:
            length = _cabinet_footprint_length_from_points(points)
        else:
            length = _outline_width_from_points(points)
    else:
        length = _polyline_length(points)
    if length <= 0:
        return None
    attrs = _fixture_attributes(entity)
    fixture_type = fixture_type_override or _fixture_text_attribute(attrs, _FIXTURE_TYPE_ATTRIBUTE_KEYS)
    room = _fixture_text_attribute(attrs, _FIXTURE_ROOM_ATTRIBUTE_KEYS)
    room_id = _fixture_text_attribute(attrs, _FIXTURE_ROOM_ID_ATTRIBUTE_KEYS)
    marker_attrs = dict(attrs)
    if fixture_type_override is not None:
        marker_attrs["TYPE"] = fixture_type_override
    if room is not None:
        marker_attrs["ROOM"] = room
    return FixtureMarker(
        id=_entity_id(entity),
        layer=layer,
        kind=kind,
        points=points,
        length=length,
        height=_fixture_height_from_attributes(attrs),
        fixture_type=fixture_type,
        room_id=room_id,
        attributes=marker_attrs,
    )


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


def _insert_attributes(entity) -> dict[str, str]:
    return {
        str(attrib.dxf.tag).strip().lower(): str(attrib.dxf.text).strip()
        for attrib in getattr(entity, "attribs", [])
        if str(attrib.dxf.tag).strip()
    }


def _xdata_key_value_attributes(entity, appids: tuple[str, ...]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for appid in appids:
        if not entity.has_xdata(appid):
            continue
        for tag in entity.get_xdata(appid):
            value = getattr(tag, "value", None)
            if not isinstance(value, str) or "=" not in value:
                continue
            key, text = value.split("=", 1)
            key = key.strip()
            text = text.strip()
            if key:
                attributes[key] = text
    return attributes


def _fixture_attributes(entity) -> dict[str, str]:
    return _xdata_key_value_attributes(entity, _FIXTURE_XDATA_APPIDS)


def _construction_attributes(entity) -> dict[str, str]:
    attrs = _xdata_key_value_attributes(entity, _FIXTURE_XDATA_APPIDS)
    attrs.update(_insert_attributes(entity))
    return attrs


def _parse_boolean(value: str) -> bool | None:
    cleaned = value.strip().lower()
    if cleaned in {"true", "1", "yes", "y", "on"}:
        return True
    if cleaned in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _exterior_wall_attributes(entity) -> dict[str, bool]:
    attrs = _xdata_key_value_attributes(entity, _FIXTURE_XDATA_APPIDS)
    for key in ("QUOTE_INCLUDE", "INCLUDE", "quote_include", "include"):
        if key not in attrs:
            continue
        include = _parse_boolean(attrs[key])
        if include is not None:
            return {"include_in_quote": include}
    return {}


def _dimension_from_attributes(attrs: dict[str, str], keys: tuple[str, ...]) -> float | None:
    normalized = {str(key).lower(): value for key, value in attrs.items()}
    for key in keys:
        value = normalized.get(key.lower())
        if value is None:
            continue
        parsed = _parse_window_dimension(value)
        if parsed is not None:
            return round(parsed, 6)
    return None


def _construction_marker_from_points(
    entity,
    points: list[Point],
    layer: LayerName,
    kind: ConstructionKind,
) -> ConstructionMarker | None:
    if not points:
        return None
    attrs = _construction_attributes(entity)
    return ConstructionMarker(
        id=_entity_id(entity),
        layer=layer,
        kind=kind,
        points=points,
        length=_polyline_length(points) if len(points) >= 2 else 0.0,
        height=_dimension_from_attributes(attrs, _CONSTRUCTION_HEIGHT_ATTRIBUTE_KEYS),
        thickness=_dimension_from_attributes(attrs, _CONSTRUCTION_THICKNESS_ATTRIBUTE_KEYS),
        attributes=dict(attrs),
    )


def _parse_window_dimension(value: str) -> float | None:
    cleaned = value.strip().lower().replace(" ", "")
    if not cleaned:
        return None

    factor = 1.0
    if cleaned.endswith("mm"):
        cleaned = cleaned[:-2]
        factor = 0.001
    elif cleaned.endswith("m"):
        cleaned = cleaned[:-1]

    try:
        number = float(cleaned)
    except ValueError:
        return None

    dimension = number * factor
    if factor == 1.0 and number > 20:
        dimension = number * 0.001
    if dimension <= 0:
        return None
    return dimension


def _window_dimension_from_attributes(attrs: dict[str, str], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = attrs.get(key)
        if value is not None:
            return _parse_window_dimension(value)
    return None


def _fixture_text_attribute(attrs: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = attrs.get(key)
        if value:
            return value
    return None


def _fixture_height_from_attributes(attrs: dict[str, str]) -> float | None:
    for key in _FIXTURE_HEIGHT_ATTRIBUTE_KEYS:
        value = attrs.get(key)
        if value is None:
            continue
        return _parse_window_dimension(value)
    return None


def _text_value(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return str(entity.dxf.text).strip()


def _parse_float_text(value: str) -> float | None:
    return _parse_window_dimension(value)


def _polygon_from_room(room: RoomBoundary) -> Polygon:
    return Polygon((point.x, point.y) for point in room.points)


def _assign_text_names(rooms: list[RoomBoundary], texts: list[TextMarker]) -> None:
    for room in rooms:
        polygon = _polygon_from_room(room)
        matches = [text for text in texts if polygon.contains(ShapelyPoint(text.point.x, text.point.y))]
        if len(matches) == 1:
            room.name = matches[0].text


def _assign_room_floors(
    rooms: list[RoomBoundary], floor_markers: list[TextMarker], issues: list[AdapterIssue]
) -> None:
    for room in rooms:
        polygon = _polygon_from_room(room)
        matches = [
            marker
            for marker in floor_markers
            if polygon.covers(ShapelyPoint(marker.point.x, marker.point.y))
        ]
        if len(matches) == 1:
            room.floor = matches[0].text
            continue
        if len(matches) > 1:
            marker_ids = ", ".join(marker.id for marker in matches)
            issues.append(
                AdapterIssue(
                    code="ROOM_FLOOR_AMBIGUOUS",
                    message=f"Room {room.id} contains multiple QUOTE_FLOOR markers: {marker_ids}.",
                    entity_id=room.id,
                    layer=LayerName.QUOTE_FLOOR.value,
                )
            )


def _matching_room_floors_for_point(point: Point, rooms: list[RoomBoundary]) -> set[str]:
    marker_point = ShapelyPoint(point.x, point.y)
    floors: set[str] = set()
    for room in rooms:
        if not room.floor:
            continue
        polygon = _polygon_from_room(room)
        if polygon.covers(marker_point) or polygon.distance(marker_point) <= _FLOOR_POINT_MATCH_TOLERANCE_METERS:
            floors.add(room.floor)
    return floors


def _matching_room_floors_for_polyline(points: list[Point], rooms: list[RoomBoundary]) -> set[str]:
    if len(points) == 1:
        return _matching_room_floors_for_point(points[0], rooms)
    marker_line = LineString((point.x, point.y) for point in points)
    floors: set[str] = set()
    for room in rooms:
        if not room.floor:
            continue
        polygon = _polygon_from_room(room)
        if polygon.intersects(marker_line) or polygon.distance(marker_line) <= _FLOOR_LINE_MATCH_TOLERANCE_METERS:
            floors.add(room.floor)
    return floors


def _assign_imported_marker_floors(
    rooms: list[RoomBoundary],
    windows: list[WindowMarker],
    doors: list[DoorMarker],
    heights: list[HeightMarker],
    walls: list[PolylineMarker],
    openings: list[PolylineMarker],
    voids: list[VoidMarker],
    exterior_walls: list[PolylineMarker],
    exterior_openings: list[PolylineMarker],
    building_areas: list[PolylineMarker],
    custom_items: list[FixtureMarker],
    cabinet_items: list[FixtureMarker],
    demo_walls: list[ConstructionMarker],
    new_walls: list[ConstructionMarker],
    lintels: list[ConstructionMarker],
    lintel_holes: list[ConstructionMarker],
    pipe_insulations: list[ConstructionMarker],
    pipe_wraps: list[ConstructionMarker],
    exterior_repairs: list[ConstructionMarker],
    wall_tiles: list[ConstructionMarker],
    background_walls: list[ConstructionMarker],
) -> None:
    for marker in [*windows, *doors, *heights]:
        if marker.floor is not None:
            continue
        floors = _matching_room_floors_for_point(marker.point, rooms)
        if len(floors) == 1:
            marker.floor = next(iter(floors))

    for marker in [
        *walls,
        *openings,
        *voids,
        *exterior_walls,
        *exterior_openings,
        *building_areas,
        *custom_items,
        *cabinet_items,
        *demo_walls,
        *new_walls,
        *lintels,
        *lintel_holes,
        *pipe_insulations,
        *pipe_wraps,
        *exterior_repairs,
        *wall_tiles,
        *background_walls,
    ]:
        if marker.floor is not None:
            continue
        floors = _matching_room_floors_for_polyline(marker.points, rooms)
        if len(floors) == 1:
            marker.floor = next(iter(floors))


def _filter_rooms_by_matched_text(
    rooms: list[RoomBoundary], texts: list[TextMarker], issues: list[AdapterIssue]
) -> list[RoomBoundary]:
    if not texts or not any(room.name for room in rooms):
        return rooms

    filtered_rooms: list[RoomBoundary] = []
    for room in rooms:
        if room.name:
            filtered_rooms.append(room)
            continue
        issues.append(
            AdapterIssue(
                code="ROOM_BOUNDARY_WITHOUT_TEXT_IGNORED",
                message="Room boundary ignored because QUOTE_TEXT matched other room boundaries in this drawing.",
                entity_id=room.id,
                layer=LayerName.QUOTE_ROOM.value,
            )
        )
    return filtered_rooms


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
    ordinary_texts: list[TextMarker] = []
    floor_markers: list[TextMarker] = []
    windows: list[WindowMarker] = []
    doors: list[DoorMarker] = []
    walls: list[PolylineMarker] = []
    openings: list[PolylineMarker] = []
    heights: list[HeightMarker] = []
    voids: list[VoidMarker] = []
    exterior_walls: list[PolylineMarker] = []
    exterior_openings: list[PolylineMarker] = []
    building_areas: list[PolylineMarker] = []
    custom_items: list[FixtureMarker] = []
    cabinet_items: list[FixtureMarker] = []
    demo_walls: list[ConstructionMarker] = []
    new_walls: list[ConstructionMarker] = []
    lintels: list[ConstructionMarker] = []
    lintel_holes: list[ConstructionMarker] = []
    pipe_insulations: list[ConstructionMarker] = []
    pipe_wraps: list[ConstructionMarker] = []
    exterior_repairs: list[ConstructionMarker] = []
    wall_tiles: list[ConstructionMarker] = []
    background_walls: list[ConstructionMarker] = []

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
        elif entity.dxftype() in {"TEXT", "MTEXT"} and layer not in _QUOTE_LAYER_NAMES:
            value = _text_value(entity)
            if value:
                ordinary_texts.append(
                    TextMarker(id=_entity_id(entity), text=value, point=_text_point(entity, options.confirmed_unit))
                )
        elif layer == LayerName.QUOTE_FLOOR.value and entity.dxftype() in {"TEXT", "MTEXT"}:
            value = _text_value(entity)
            if value:
                floor_markers.append(
                    TextMarker(
                        id=_entity_id(entity),
                        layer=LayerName.QUOTE_FLOOR,
                        text=value,
                        point=_text_point(entity, options.confirmed_unit),
                    )
                )
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
        elif layer == LayerName.QUOTE_WINDOW.value and entity.dxftype() == "INSERT":
            attrs = _insert_attributes(entity)
            width = _window_dimension_from_attributes(attrs, _WINDOW_WIDTH_ATTRIBUTE_KEYS)
            height = _window_dimension_from_attributes(attrs, _WINDOW_HEIGHT_ATTRIBUTE_KEYS)
            if width is None:
                issues.append(
                    AdapterIssue(
                        code="WINDOW_WIDTH_ATTRIBUTE_INVALID",
                        message="Window block must have a parseable width attribute.",
                        entity_id=_entity_id(entity),
                        layer=layer,
                    )
                )
                continue
            windows.append(
                WindowMarker(
                    id=_entity_id(entity),
                    point=_insert_point(entity, options.confirmed_unit),
                    width=width,
                    height=height,
                    attributes={"source": "insert_attributes", "block_name": str(entity.dxf.name)},
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
            attrs = _insert_attributes(entity)
            width = _window_dimension_from_attributes(attrs, _DOOR_WIDTH_ATTRIBUTE_KEYS)
            height = _window_dimension_from_attributes(attrs, _DOOR_HEIGHT_ATTRIBUTE_KEYS)
            source = "insert_attributes" if width is not None else "insert"
            if width is None:
                width = _insert_width(entity, options.confirmed_unit)
            if width is not None:
                doors.append(
                    DoorMarker(
                        id=_entity_id(entity),
                        point=_insert_point(entity, options.confirmed_unit),
                        width=width,
                        height=height,
                        attributes={"source": source, "block_name": str(entity.dxf.name)},
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
        elif layer == LayerName.QUOTE_CUSTOM.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _fixture_marker_from_points(entity, points, LayerName.QUOTE_CUSTOM, FixtureKind.CUSTOM)
            if marker is not None:
                custom_items.append(marker)
        elif layer == LayerName.QUOTE_CABINET.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _fixture_marker_from_points(entity, points, LayerName.QUOTE_CABINET, FixtureKind.CABINET)
            if marker is not None:
                cabinet_items.append(marker)
        elif layer in {LayerName.QUOTE_BASE_CABINET.value, LayerName.QUOTE_WALL_CABINET.value} and entity.dxftype() in {
            "LINE",
            "LWPOLYLINE",
        }:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker_layer = LayerName(layer)
            fixture_type = "地柜" if marker_layer is LayerName.QUOTE_BASE_CABINET else "吊柜"
            marker = _fixture_marker_from_points(
                entity,
                points,
                marker_layer,
                FixtureKind.CABINET,
                fixture_type_override=fixture_type,
            )
            if marker is not None:
                cabinet_items.append(marker)
        elif layer == LayerName.QUOTE_DEMO_WALL.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity, points, LayerName.QUOTE_DEMO_WALL, ConstructionKind.DEMO_WALL
            )
            if marker is not None and marker.length > 0:
                demo_walls.append(marker)
        elif layer == LayerName.QUOTE_NEW_WALL.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity, points, LayerName.QUOTE_NEW_WALL, ConstructionKind.NEW_WALL
            )
            if marker is not None and marker.length > 0:
                new_walls.append(marker)
        elif layer == LayerName.QUOTE_LINTEL.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity, points, LayerName.QUOTE_LINTEL, ConstructionKind.LINTEL
            )
            if marker is not None:
                lintels.append(marker)
        elif layer == LayerName.QUOTE_LINTEL_HOLE.value and entity.dxftype() in {"POINT", "INSERT", "LINE", "LWPOLYLINE"}:
            if entity.dxftype() == "POINT":
                point = entity.dxf.location
                points = [_point(point.x, point.y, options.confirmed_unit)]
            elif entity.dxftype() == "INSERT":
                points = [_insert_point(entity, options.confirmed_unit)]
            elif entity.dxftype() == "LINE":
                points = _line_points(entity, options.confirmed_unit)
            else:
                points = _lwpolyline_points(entity, options.confirmed_unit)
            marker = _construction_marker_from_points(
                entity, points, LayerName.QUOTE_LINTEL_HOLE, ConstructionKind.LINTEL_HOLE
            )
            if marker is not None:
                lintel_holes.append(marker)
        elif layer in {LayerName.QUOTE_PIPE_INSULATION.value, LayerName.QUOTE_PIPE_WRAP.value} and entity.dxftype() in {
            "POINT",
            "INSERT",
            "LINE",
            "LWPOLYLINE",
        }:
            if entity.dxftype() == "POINT":
                point = entity.dxf.location
                points = [_point(point.x, point.y, options.confirmed_unit)]
            elif entity.dxftype() == "INSERT":
                points = [_insert_point(entity, options.confirmed_unit)]
            elif entity.dxftype() == "LINE":
                points = _line_points(entity, options.confirmed_unit)
            else:
                points = _lwpolyline_points(entity, options.confirmed_unit)
            if layer == LayerName.QUOTE_PIPE_INSULATION.value:
                marker = _construction_marker_from_points(
                    entity,
                    points,
                    LayerName.QUOTE_PIPE_INSULATION,
                    ConstructionKind.PIPE_INSULATION,
                )
                if marker is not None:
                    pipe_insulations.append(marker)
            else:
                marker = _construction_marker_from_points(
                    entity,
                    points,
                    LayerName.QUOTE_PIPE_WRAP,
                    ConstructionKind.PIPE_WRAP,
                )
                if marker is not None:
                    pipe_wraps.append(marker)
        elif layer == LayerName.QUOTE_EXT_REPAIR.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity,
                points,
                LayerName.QUOTE_EXT_REPAIR,
                ConstructionKind.EXTERIOR_REPAIR,
            )
            if marker is not None and marker.length > 0:
                exterior_repairs.append(marker)
        elif layer == LayerName.QUOTE_WALL_TILE.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity,
                points,
                LayerName.QUOTE_WALL_TILE,
                ConstructionKind.WALL_TILE,
            )
            if marker is not None and marker.length > 0:
                wall_tiles.append(marker)
        elif layer == LayerName.QUOTE_BACKGROUND_WALL.value and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            points = (
                _line_points(entity, options.confirmed_unit)
                if entity.dxftype() == "LINE"
                else _lwpolyline_points(entity, options.confirmed_unit)
            )
            marker = _construction_marker_from_points(
                entity,
                points,
                LayerName.QUOTE_BACKGROUND_WALL,
                ConstructionKind.BACKGROUND_WALL,
            )
            if marker is not None and marker.length > 0:
                background_walls.append(marker)
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
                exterior_walls.append(
                    PolylineMarker(
                        id=_entity_id(entity),
                        layer=LayerName.QUOTE_EXT_WALL,
                        points=points,
                        attributes=_exterior_wall_attributes(entity),
                    )
                )
        elif layer == LayerName.QUOTE_EXT_OPENING.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 2:
                exterior_openings.append(
                    PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_EXT_OPENING, points=points)
                )
        elif layer == LayerName.QUOTE_BUILDING_AREA.value and entity.dxftype() == "LWPOLYLINE":
            points = _lwpolyline_points(entity, options.confirmed_unit)
            if len(points) >= 4 and points[0] == points[-1] and _valid_room_polygon(points):
                building_areas.append(
                    PolylineMarker(id=_entity_id(entity), layer=LayerName.QUOTE_BUILDING_AREA, points=points)
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

    if not texts:
        texts = ordinary_texts

    _assign_text_names(rooms, texts)
    _assign_room_floors(rooms, floor_markers, issues)
    rooms = _filter_rooms_by_matched_text(rooms, texts, issues)
    _assign_imported_marker_floors(
        rooms,
        windows,
        doors,
        heights,
        walls,
        openings,
        voids,
        exterior_walls,
        exterior_openings,
        building_areas,
        custom_items,
        cabinet_items,
        demo_walls,
        new_walls,
        lintels,
        lintel_holes,
        pipe_insulations,
        pipe_wraps,
        exterior_repairs,
        wall_tiles,
        background_walls,
    )
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
        building_areas=building_areas,
        custom_items=custom_items,
        cabinet_items=cabinet_items,
        demo_walls=demo_walls,
        new_walls=new_walls,
        lintels=lintels,
        lintel_holes=lintel_holes,
        pipe_insulations=pipe_insulations,
        pipe_wraps=pipe_wraps,
        exterior_repairs=exterior_repairs,
        wall_tiles=wall_tiles,
        background_walls=background_walls,
    )
    return CadImportResult(project=project, issues=issues, source_path=options.source_path, dxf_path=options.source_path)
