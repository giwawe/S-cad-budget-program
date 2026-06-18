from cad_budget.geometry import (
    closed_polygon_area,
    closed_polygon_perimeter,
    point_inside_polygon,
    polyline_length,
)
from cad_budget.models import Point


RECT = [
    Point(x=0, y=0),
    Point(x=4, y=0),
    Point(x=4, y=3),
    Point(x=0, y=3),
    Point(x=0, y=0),
]


def test_closed_polygon_area_and_perimeter():
    assert closed_polygon_area(RECT) == 12
    assert closed_polygon_perimeter(RECT) == 14


def test_polyline_length_for_opening():
    line = [Point(x=0, y=0), Point(x=3, y=4)]
    assert polyline_length(line) == 5


def test_point_inside_polygon():
    assert point_inside_polygon(Point(x=2, y=1), RECT) is True
    assert point_inside_polygon(Point(x=5, y=1), RECT) is False
