"""Tests for the pure shot-cone geometry: the triangle from a shot's origin to both posts and who stands in it.

Points are placed by hand in the shooter's attacking frame, so every inside or outside answer can be checked exactly.
They cover the post coordinates, edge and vertex inclusion, keeper flagging, empty input, and points behind the shooter.
"""

import pytest

from insidegame.analytics.shot_cone import ConeOccupancy, cone_occupancy, cone_points, in_triangle
from insidegame.core.geometry import Point

ORIGIN = Point(90.0, 34.0)
JUST_OUTSIDE_M = 0.01


def test_cone_points_are_the_origin_and_both_posts() -> None:
    origin, near, far = cone_points(ORIGIN)
    assert origin == ORIGIN
    assert near.x == far.x == 105.0
    assert near.y == pytest.approx(30.34) and far.y == pytest.approx(37.66)


def test_points_on_edges_and_vertices_count_as_inside() -> None:
    a, b, c = Point(0.0, 0.0), Point(10.0, 0.0), Point(0.0, 10.0)
    for point in (a, b, c, Point(5.0, 0.0), Point(0.0, 5.0), Point(5.0, 5.0), Point(2.0, 2.0)):
        assert in_triangle(point, a, b, c)


def test_points_just_outside_are_outside() -> None:
    a, b, c = Point(0.0, 0.0), Point(10.0, 0.0), Point(0.0, 10.0)
    for point in (Point(5.0, -JUST_OUTSIDE_M), Point(-JUST_OUTSIDE_M, 5.0), Point(5.0 + JUST_OUTSIDE_M, 5.0),
                  Point(11.0, 0.0)):
        assert not in_triangle(point, a, b, c)


def test_occupancy_counts_outfield_inside_and_flags_the_keeper_only_when_inside() -> None:
    inside = [Point(100.0, 34.0), Point(97.0, 33.0)]
    outside = [Point(100.0, 45.0), Point(80.0, 34.0)]
    assert cone_occupancy(ORIGIN, inside + outside, Point(104.0, 34.0)) == ConeOccupancy(2, True)
    assert cone_occupancy(ORIGIN, inside, Point(104.0, 45.0)) == ConeOccupancy(2, False)


def test_empty_input_gives_no_defenders_and_no_keeper() -> None:
    assert cone_occupancy(ORIGIN, [], None) == ConeOccupancy(0, False)


def test_points_behind_the_shooter_are_never_counted() -> None:
    behind = [Point(ORIGIN.x - 0.5, ORIGIN.y), Point(ORIGIN.x - 5.0, 33.0), Point(60.0, 34.0)]
    assert cone_occupancy(ORIGIN, behind, Point(ORIGIN.x - 1.0, ORIGIN.y)) == ConeOccupancy(0, False)
