"""Tests for the pure offside rule applied to tracked formation shapes.

Points are built by hand in the attacking team's frame (attacking toward x = 105), so every line is checked exactly.
They cover the second-last defender, the ball, the halfway floor, the margin, and attackers already onside.
"""

from insidegame.core.geometry import Point
from insidegame.tracking.offside import HALFWAY_X_M, ONSIDE_MARGIN_M, offside_line, onside_positions

KEEPER = Point(103.5, 34.0)
LAST_DEFENDER = Point(96.0, 30.0)


def test_the_line_is_the_second_last_defender() -> None:
    assert offside_line([KEEPER, LAST_DEFENDER, Point(80.0, 40.0)], Point(70.0, 34.0)) == 96.0


def test_the_ball_moves_the_line_when_it_is_further_forward() -> None:
    assert offside_line([KEEPER, LAST_DEFENDER], Point(99.0, 34.0)) == 99.0


def test_the_line_never_falls_inside_the_attackers_own_half() -> None:
    assert offside_line([Point(40.0, 30.0), Point(30.0, 30.0)], Point(20.0, 34.0)) == HALFWAY_X_M


def test_a_striker_on_the_goal_line_is_held_just_onside() -> None:
    striker, winger = Point(105.0, 34.7), Point(90.0, 10.0)
    held = onside_positions([striker, winger], [KEEPER, LAST_DEFENDER], Point(88.0, 27.0))
    assert held[0] == Point(96.0 - ONSIDE_MARGIN_M, 34.7)
    assert held[1] == winger
