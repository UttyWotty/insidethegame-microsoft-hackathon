"""Tests for the pure replay motion smoothing: off-ball speed caps, fixed anchors, and rounding.

Steps are built by hand with one or two players, so every shown spot can be checked exactly.
They pin that slow moves are untouched, fast moves are pulled within reach of both neighbours, players on the ball
and the last step never move, and the cap gives way only between two anchors too far apart to run.
"""

import math

import pytest

from insidegame.highlights.replay_motion import MAX_OFF_BALL_SPEED_MS, MotionStep, capped_positions

FAR_BALL = (100.0, 60.0)
SPEED = 5.0


def _spot(frame: list[tuple[str, float, float]], player_id: str) -> tuple[float, float]:
    return next((x, y) for pid, x, y in frame if pid == player_id)


def test_slow_moves_keep_the_tracked_positions() -> None:
    steps = [MotionStep(0.0, FAR_BALL, [("a", 10.0, 10.0)]), MotionStep(2.0, FAR_BALL, [("a", 18.0, 10.0)])]
    assert capped_positions(steps, SPEED) == [[("a", 10.0, 10.0)], [("a", 18.0, 10.0)]]


def test_a_fast_off_ball_move_is_capped_and_the_last_step_stays_true() -> None:
    steps = [MotionStep(0.0, FAR_BALL, [("a", 10.0, 10.0)]), MotionStep(1.0, FAR_BALL, [("a", 40.0, 10.0)]),
             MotionStep(3.0, FAR_BALL, [("a", 40.0, 10.0)])]
    shown = capped_positions(steps, SPEED)
    assert _spot(shown[2], "a") == (40.0, 10.0)
    for before, after, step_s in ((shown[0], shown[1], 1.0), (shown[1], shown[2], 2.0)):
        assert math.dist(_spot(before, "a"), _spot(after, "a")) <= SPEED * step_s + 0.1


def test_a_player_on_the_ball_is_never_moved() -> None:
    steps = [MotionStep(0.0, (10.0, 10.0), [("a", 10.0, 10.0)]), MotionStep(1.0, FAR_BALL, [("a", 40.0, 10.0)]),
             MotionStep(7.0, FAR_BALL, [("a", 40.0, 10.0)])]
    shown = capped_positions(steps, SPEED)
    assert _spot(shown[0], "a") == (10.0, 10.0)
    assert math.dist(_spot(shown[0], "a"), _spot(shown[1], "a")) <= SPEED + 0.1


def test_two_anchors_too_far_apart_keep_their_spots() -> None:
    steps = [MotionStep(0.0, (10.0, 10.0), [("a", 10.0, 10.0)]), MotionStep(1.0, FAR_BALL, [("a", 60.0, 10.0)])]
    assert capped_positions(steps, SPEED) == [[("a", 10.0, 10.0)], [("a", 60.0, 10.0)]]


def test_every_player_is_smoothed_on_their_own_and_shown_rounded() -> None:
    steps = [MotionStep(0.0, FAR_BALL, [("a", 10.0, 10.0), ("b", 1.04, 2.06)]),
             MotionStep(1.0, FAR_BALL, [("a", 30.0, 10.0), ("b", 1.04, 2.06)]),
             MotionStep(2.0, FAR_BALL, [("a", 30.0, 10.0), ("b", 1.04, 2.06)])]
    shown = capped_positions(steps, SPEED)
    assert [_spot(f, "b") for f in shown] == [(1.0, 2.1)] * 3
    assert _spot(shown[1], "a")[0] == pytest.approx(25.0, abs=0.1)


def test_the_cap_is_a_running_speed() -> None:
    assert 6.0 <= MAX_OFF_BALL_SPEED_MS <= 9.0
