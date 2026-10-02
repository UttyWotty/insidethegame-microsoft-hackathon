"""Tests for pure pitch geometry helpers in insidegame.core.geometry.

They check distances, goal angles, clamping, and perspective mirroring.
No I/O or randomness is involved.
"""

import math

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import (
    GOAL_CENTER,
    Point,
    clamp_to_pitch,
    distance,
    distance_to_goal,
    goal_angle,
    mirror,
)


def test_distance_is_euclidean() -> None:
    assert distance(Point(0, 0), Point(3, 4)) == 5


def test_distance_to_goal_is_zero_at_goal_center() -> None:
    assert distance_to_goal(GOAL_CENTER) == 0


def test_goal_angle_shrinks_with_distance() -> None:
    near = goal_angle(Point(PITCH_LENGTH_M - 6, PITCH_WIDTH_M / 2))
    far = goal_angle(Point(PITCH_LENGTH_M - 30, PITCH_WIDTH_M / 2))
    assert near > far > 0


def test_goal_angle_is_smaller_from_wide_positions() -> None:
    central = goal_angle(Point(90, PITCH_WIDTH_M / 2))
    wide = goal_angle(Point(90, 5))
    assert central > wide


def test_clamp_to_pitch_bounds_coordinates() -> None:
    assert clamp_to_pitch(Point(-5, 80)) == Point(0, PITCH_WIDTH_M)


def test_mirror_is_an_involution() -> None:
    p = Point(12.5, 40.0)
    assert mirror(mirror(p)) == p
    assert math.isclose(mirror(p).x, PITCH_LENGTH_M - 12.5)
