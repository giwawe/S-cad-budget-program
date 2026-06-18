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


def polyline_length(points: list[Point]) -> float:
    return round(sum(hypot(b.x - a.x, b.y - a.y) for a, b in _pairs(points)), 6)


def closed_polygon_area(points: list[Point]) -> float:
    polygon = Polygon([(point.x, point.y) for point in points])
    return round(float(polygon.area), 6)


def closed_polygon_perimeter(points: list[Point]) -> float:
    return polyline_length(points)

def point_inside_polygon(point: Point, polygon_points: list[Point]) -> bool:
    polygon = Polygon([(p.x, p.y) for p in polygon_points])
    return bool(polygon.contains(ShapelyPoint(point.x, point.y)))
