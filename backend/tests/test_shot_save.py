"""Tests for the pure saved-shot geometry: where the ball stops on the line from the shot origin to its placement.

Keepers and origins are placed by hand in the shooter's attacking frame, so each stop can be checked exactly.
They cover the keeper's depth, the default without a keeper, clamping at both ends, the minimum flight, the depth rule
winning close to the line, and a sweep that every stop is strictly short of the goal line.
"""

import pytest

from insidegame.analytics.shot_save import (
    SAVE_DEFAULT_DEPTH_M,
    SAVE_MAX_DEPTH_M,
    SAVE_MIN_DEPTH_M,
    SAVE_MIN_FLIGHT_M,
    save_depth,
    save_point,
)
from insidegame.core.constants import GOAL_CENTER_Y_M, GOAL_WIDTH_M, PITCH_LENGTH_M
from insidegame.core.geometry import Point, distance

ORIGIN = Point(90.0, GOAL_CENTER_Y_M)
LINE_TOLERANCE_M = 1e-9


def _on_shot_line(origin: Point, placement_y: float, stop: Point) -> bool:
    """Whether stop lies on the segment from origin to the placement on the goal line."""
    target = Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M + placement_y)
    return distance(origin, stop) + distance(stop, target) == pytest.approx(distance(origin, target))


def test_the_ball_stops_at_the_keepers_distance_off_the_line() -> None:
    stop = save_point(ORIGIN, 0.0, Point(PITCH_LENGTH_M - 1.8, 35.0))
    assert stop == pytest.approx(Point(PITCH_LENGTH_M - 1.8, GOAL_CENTER_Y_M))


def test_an_angled_save_stops_on_the_shot_line_at_the_keepers_depth() -> None:
    origin = Point(92.0, 26.0)
    stop = save_point(origin, 2.5, Point(PITCH_LENGTH_M - 1.2, 36.0))
    assert stop.x == pytest.approx(PITCH_LENGTH_M - 1.2)
    assert _on_shot_line(origin, 2.5, stop)


def test_without_a_keeper_the_ball_stops_the_default_depth_out() -> None:
    assert save_depth(None) == SAVE_DEFAULT_DEPTH_M
    stop = save_point(ORIGIN, -1.5, None)
    assert stop.x == pytest.approx(PITCH_LENGTH_M - SAVE_DEFAULT_DEPTH_M)
    assert _on_shot_line(ORIGIN, -1.5, stop)


def test_a_keeper_on_or_behind_the_line_is_clamped_to_the_minimum_depth() -> None:
    for keeper_x in (PITCH_LENGTH_M, PITCH_LENGTH_M + 0.5, PITCH_LENGTH_M - 0.1):
        assert save_depth(Point(keeper_x, GOAL_CENTER_Y_M)) == SAVE_MIN_DEPTH_M
        assert save_point(ORIGIN, 0.0, Point(keeper_x, GOAL_CENTER_Y_M)).x == pytest.approx(
            PITCH_LENGTH_M - SAVE_MIN_DEPTH_M)


def test_a_keeper_far_off_the_line_is_clamped_to_the_maximum_depth() -> None:
    keeper = Point(PITCH_LENGTH_M - 8.0, GOAL_CENTER_Y_M)
    assert save_depth(keeper) == SAVE_MAX_DEPTH_M
    assert save_point(ORIGIN, 0.0, keeper) == pytest.approx(Point(PITCH_LENGTH_M - SAVE_MAX_DEPTH_M, GOAL_CENTER_Y_M))


def test_the_flight_is_at_least_the_minimum_when_the_shooter_is_past_the_save_depth() -> None:
    origin = Point(PITCH_LENGTH_M - 2.0, GOAL_CENTER_Y_M)
    stop = save_point(origin, 0.0, Point(PITCH_LENGTH_M - 2.5, GOAL_CENTER_Y_M))
    assert distance(origin, stop) == pytest.approx(SAVE_MIN_FLIGHT_M)
    assert _on_shot_line(origin, 0.0, stop)


def test_the_depth_rule_wins_over_the_minimum_flight_for_a_shooter_very_close_to_the_line() -> None:
    origin = Point(PITCH_LENGTH_M - 0.6, GOAL_CENTER_Y_M + 0.2)
    stop = save_point(origin, 0.0, Point(PITCH_LENGTH_M - 2.0, GOAL_CENTER_Y_M))
    assert stop.x == pytest.approx(PITCH_LENGTH_M - SAVE_MIN_DEPTH_M)
    assert distance(origin, stop) < SAVE_MIN_FLIGHT_M
    assert _on_shot_line(origin, 0.0, stop)


def test_a_shot_from_inside_the_minimum_depth_stops_at_its_origin() -> None:
    origin = Point(PITCH_LENGTH_M - 0.1, GOAL_CENTER_Y_M)
    assert save_point(origin, 1.0, None) == origin


def test_every_stop_is_strictly_short_of_the_goal_line_between_the_posts() -> None:
    half = GOAL_WIDTH_M / 2
    placements = [-half + 0.1, -1.0, 0.0, 1.5, half - 0.1]
    keepers: list[Point | None] = [None, Point(PITCH_LENGTH_M + 1.0, 30.0), Point(104.0, 34.0), Point(90.0, 40.0)]
    for x in (80.0, 94.0, 100.0, 103.0, 104.5, 104.69):
        for y in (GOAL_CENTER_Y_M - half + 0.2, 32.0, GOAL_CENTER_Y_M, GOAL_CENTER_Y_M + half - 0.2):
            for placement in placements:
                for keeper in keepers:
                    stop = save_point(Point(x, y), placement, keeper)
                    assert stop.x <= PITCH_LENGTH_M - SAVE_MIN_DEPTH_M + LINE_TOLERANCE_M
                    assert GOAL_CENTER_Y_M - half < stop.y < GOAL_CENTER_Y_M + half
                    assert _on_shot_line(Point(x, y), placement, stop)


def test_a_keeper_wide_of_the_posts_sets_the_depth_from_his_distance_off_the_line_only() -> None:
    wide = Point(PITCH_LENGTH_M - 2.0, GOAL_CENTER_Y_M - 20.0)
    centred = Point(PITCH_LENGTH_M - 2.0, GOAL_CENTER_Y_M)
    assert save_point(ORIGIN, 1.0, wide) == save_point(ORIGIN, 1.0, centred)


def test_a_shot_at_either_post_stops_inside_the_posts_on_its_line() -> None:
    half = GOAL_WIDTH_M / 2
    for placement in (-half, half):
        stop = save_point(ORIGIN, placement, None)
        assert abs(stop.y - GOAL_CENTER_Y_M) < half
        assert _on_shot_line(ORIGIN, placement, stop)


def test_a_keeper_further_out_than_the_shooter_still_stops_the_ball_ahead_of_the_shooter() -> None:
    origin = Point(PITCH_LENGTH_M - 5.0, GOAL_CENTER_Y_M)
    stop = save_point(origin, 0.0, Point(PITCH_LENGTH_M - 10.0, GOAL_CENTER_Y_M))
    assert stop == pytest.approx(Point(PITCH_LENGTH_M - SAVE_MAX_DEPTH_M, GOAL_CENTER_Y_M))
