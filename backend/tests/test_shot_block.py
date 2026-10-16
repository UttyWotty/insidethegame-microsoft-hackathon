"""Tests for the pure blocked-shot geometry: where the ball stops along the line from the shot origin to the goal.

Defenders are placed by hand in the shooter's attacking frame, so each projected stop can be checked exactly.
They cover the nearest blocker in the lane, players behind the shooter, outside the lane or past the goal, the fallback,
the minimum blocker gap, the minimum flight, and the goal-line clearance that wins over both.
"""

import pytest

from insidegame.analytics.shot_block import (
    BLOCK_FALLBACK_M,
    BLOCK_GOAL_CLEARANCE_M,
    BLOCK_LANE_M,
    BLOCK_MIN_FLIGHT_M,
    BLOCK_MIN_GAP_M,
    block_point,
)
from insidegame.core.geometry import GOAL_CENTER, Point, distance

ORIGIN = Point(90.0, 34.0)
JUST_OUTSIDE_M = 0.01


def test_the_ball_stops_at_the_nearest_defender_in_the_lane_projected_onto_the_line() -> None:
    stop = block_point(ORIGIN, [Point(99.0, 34.5), Point(95.0, 33.0), Point(97.0, 35.0)])
    assert stop == pytest.approx(Point(95.0, 34.0))


def test_a_defender_on_the_lane_edge_blocks_and_one_just_outside_does_not() -> None:
    assert block_point(ORIGIN, [Point(96.0, 34.0 + BLOCK_LANE_M)]) == pytest.approx(Point(96.0, 34.0))
    outside = block_point(ORIGIN, [Point(96.0, 34.0 + BLOCK_LANE_M + JUST_OUTSIDE_M)])
    assert outside == pytest.approx(Point(ORIGIN.x + BLOCK_FALLBACK_M, 34.0))


def test_players_behind_the_shooter_level_with_them_or_past_the_goal_never_block() -> None:
    stop = block_point(ORIGIN, [Point(85.0, 34.0), Point(90.0, 34.5), Point(106.0, 34.0)])
    assert stop == pytest.approx(Point(ORIGIN.x + BLOCK_FALLBACK_M, 34.0))


def test_without_a_blocker_the_ball_stops_the_fallback_distance_along_an_angled_line() -> None:
    origin = Point(95.0, 30.0)
    stop = block_point(origin, [])
    assert distance(origin, stop) == pytest.approx(BLOCK_FALLBACK_M)
    assert distance(stop, GOAL_CENTER) == pytest.approx(distance(origin, GOAL_CENTER) - BLOCK_FALLBACK_M)


def test_a_defender_on_top_of_the_shooter_is_ignored_and_one_at_the_minimum_gap_blocks() -> None:
    on_top = Point(ORIGIN.x + BLOCK_MIN_GAP_M - JUST_OUTSIDE_M, 34.0)
    assert block_point(ORIGIN, [on_top]) == pytest.approx(Point(ORIGIN.x + BLOCK_FALLBACK_M, 34.0))
    at_gap = Point(ORIGIN.x + BLOCK_MIN_GAP_M, 34.0)
    assert block_point(ORIGIN, [on_top, at_gap]) == pytest.approx(at_gap)


def test_the_flight_is_at_least_the_minimum_length() -> None:
    stop = block_point(ORIGIN, [Point(ORIGIN.x + BLOCK_MIN_GAP_M, 34.0 + BLOCK_LANE_M)])
    assert distance(ORIGIN, stop) >= BLOCK_MIN_FLIGHT_M


def test_a_close_range_fallback_is_clamped_short_of_the_goal_line() -> None:
    origin = Point(103.0, 34.2)
    stop = block_point(origin, [])
    assert stop.x == GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M
    assert distance(origin, stop) < BLOCK_FALLBACK_M
    assert distance(stop, GOAL_CENTER) + distance(origin, stop) == pytest.approx(distance(origin, GOAL_CENTER))


def test_a_blocker_beyond_the_clearance_is_clamped_short_of_the_goal_line() -> None:
    origin = Point(100.0, 34.0)
    stop = block_point(origin, [Point(104.5, 34.0)])
    assert stop == pytest.approx(Point(GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M, 34.0))


def test_the_clearance_wins_over_the_minimum_flight_near_the_line() -> None:
    origin = Point(GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M - BLOCK_MIN_FLIGHT_M / 2, GOAL_CENTER.y)
    stop = block_point(origin, [])
    assert stop.x == GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M
    assert distance(origin, stop) < BLOCK_MIN_FLIGHT_M


def test_a_shot_from_within_the_clearance_or_the_goal_centre_stays_put() -> None:
    inside = Point(GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M / 2, 34.0)
    assert block_point(inside, []) == inside
    assert block_point(GOAL_CENTER, [Point(100.0, 34.0)]) == GOAL_CENTER
