from math import hypot

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from cad_budget.models import Point


def _pairs(points: list[Point]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def is_closed(points: list[Point]) -> bool:
    if len(points) < 2:
        return False
    return points[0].x == points[-1].x and points[0].y == points[-1].y


def _validate_closed_polygon(points: list[Point]) -> Polygon:
    if len(points) < 4:
        raise ValueError("polygon must include at least 4 points")
    if not is_closed(points):
        raise ValueError("polygon must be closed (first point equals last point)")

    polygon = Polygon([(point.x, point.y) for point in points])
    if polygon.area <= 0:
        raise ValueError("polygon must have positive area")
    if not polygon.is_valid:
        raise ValueError("polygon must be valid geometry")
    return polygon


def polyline_length(points: list[Point]) -> float:
    return round(sum(hypot(b.x - a.x, b.y - a.y) for a, b in _pairs(points)), 6)


def closed_polygon_area(points: list[Point]) -> float:
    polygon = _validate_closed_polygon(points)
    return round(float(polygon.area), 6)


def closed_polygon_perimeter(points: list[Point]) -> float:
    _validate_closed_polygon(points)
    return polyline_length(points)


def point_inside_polygon(point: Point, polygon_points: list[Point]) -> bool:
    polygon = _validate_closed_polygon(polygon_points)
    return bool(polygon.covers(ShapelyPoint(point.x, point.y)))
