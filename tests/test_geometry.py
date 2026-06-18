from cad_budget.geometry import (
    closed_polygon_area,
    closed_polygon_perimeter,
    point_inside_polygon,
    polyline_length,
)
from cad_budget.models import Point
import pytest


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
    assert point_inside_polygon(Point(x=0, y=1), RECT) is True
    assert point_inside_polygon(Point(x=5, y=1), RECT) is False


def test_non_closed_polygon_raises_for_area_and_perimeter():
    open_polygon = [
        Point(x=0, y=0),
        Point(x=4, y=0),
        Point(x=4, y=3),
        Point(x=0, y=3),
    ]
    with pytest.raises(ValueError, match="closed"):
        closed_polygon_area(open_polygon)
    with pytest.raises(ValueError, match="closed"):
        closed_polygon_perimeter(open_polygon)


def test_too_short_polygon_raises_value_error():
    with pytest.raises(ValueError, match="at least 4"):
        closed_polygon_area([])
    with pytest.raises(ValueError, match="at least 4"):
        closed_polygon_area([Point(x=0, y=0), Point(x=1, y=0), Point(x=1, y=1)])
    with pytest.raises(ValueError, match="at least 4"):
        closed_polygon_perimeter([])


def test_degenerate_polygon_raises_value_error():
    with pytest.raises(ValueError, match="positive area"):
        closed_polygon_area(
            [
                Point(x=0, y=0),
                Point(x=1, y=0),
                Point(x=2, y=0),
                Point(x=0, y=0),
            ]
        )


def test_point_inside_polygon_raises_for_invalid_polygons():
    non_closed_polygon = [
        Point(x=0, y=0),
        Point(x=4, y=0),
        Point(x=4, y=3),
        Point(x=0, y=3),
    ]
    with pytest.raises(ValueError, match="closed"):
        point_inside_polygon(Point(x=2, y=1), non_closed_polygon)

    with pytest.raises(ValueError, match="at least 4"):
        point_inside_polygon(Point(x=2, y=1), [])

    with pytest.raises(ValueError, match="positive area"):
        point_inside_polygon(
            Point(x=1, y=0),
            [
                Point(x=0, y=0),
                Point(x=1, y=0),
                Point(x=2, y=0),
                Point(x=0, y=0),
            ],
        )
