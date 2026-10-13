"""Tests for the pure player kinematics used by synthetic tracking.

They check pace-based top speeds, capped and timed steps, measured speeds, and sprint detection. All logic is pure.
"""

import math

from insidegame.core.geometry import Point
from insidegame.tracking.motion import (
    SPRINT_KMH,
    fastest_sprinter,
    speed_kmh,
    step_toward,
    timed_target,
    top_speed_kmh,
)


def test_top_speed_follows_pace_within_human_limits() -> None:
    assert top_speed_kmh(0.0) == 27.0 and top_speed_kmh(1.0) == 35.0
    assert top_speed_kmh(2.0) == 35.0 and top_speed_kmh(0.75) > top_speed_kmh(0.35)


def test_steps_are_capped_by_speed_and_elapsed_time() -> None:
    start, far = Point(0.0, 0.0), Point(100.0, 0.0)
    moved = step_toward(start, far, 36.0, 2.0)
    assert math.isclose(moved.x, 20.0) and moved.y == 0.0
    assert step_toward(start, Point(5.0, 0.0), 36.0, 2.0) == Point(5.0, 0.0)
    assert step_toward(start, far, 36.0, 0.0) == start


def test_timed_targets_arrive_exactly_when_the_action_happens() -> None:
    start, goal = Point(0.0, 0.0), Point(30.0, 0.0)
    assert timed_target(start, goal, 1.0, 3.0) == Point(10.0, 0.0)
    assert timed_target(start, goal, 3.0, 3.0) == goal


def test_speeds_and_sprints() -> None:
    assert math.isclose(speed_kmh(Point(0.0, 0.0), Point(10.0, 0.0), 1.0), 36.0)
    assert speed_kmh(Point(0.0, 0.0), Point(10.0, 0.0), 0.0) == 0.0
    assert fastest_sprinter({"a": 12.0, "b": 30.04, "c": 27.0}) == ("b", 30.0)
    assert fastest_sprinter({"a": SPRINT_KMH - 0.1}) is None and fastest_sprinter({}) is None
