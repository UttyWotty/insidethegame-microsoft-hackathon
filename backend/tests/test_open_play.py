"""Unit tests for the open-play carry stop: carry_stop_x and the CARRY_STOP_X_M band.

A carry that would end beyond the stop depth ends at the stop, and one that starts beyond it never goes backward.
Carries that end short of the stop are unchanged, and the band keeps every stop 3 to 12 m from the goal line.
"""

from insidegame.core.constants import PITCH_LENGTH_M
from insidegame.simulation.open_play import CARRY_STOP_X_M, carry_stop_x

STOP_X = 96.5
START_SHORT = 88.0
START_DEEP = 101.0
END_BEYOND = 104.0
END_SHORT = 94.0
MIN_STOP_DEPTH_M = 3.0
MAX_STOP_DEPTH_M = 12.0


def test_a_carry_beyond_the_stop_ends_at_the_stop() -> None:
    assert carry_stop_x(END_BEYOND, START_SHORT, STOP_X) == STOP_X


def test_a_carry_starting_beyond_the_stop_never_goes_backward() -> None:
    assert carry_stop_x(END_BEYOND, START_DEEP, STOP_X) == START_DEEP
    assert carry_stop_x(START_DEEP - 1.0, START_DEEP, STOP_X) == START_DEEP - 1.0


def test_a_carry_ending_before_the_stop_is_unchanged() -> None:
    assert carry_stop_x(END_SHORT, START_SHORT, STOP_X) == END_SHORT


def test_the_stop_band_sits_three_to_twelve_metres_from_the_goal_line() -> None:
    low, high = CARRY_STOP_X_M
    assert (low, high) == (93.0, 102.0)
    assert PITCH_LENGTH_M - high == MIN_STOP_DEPTH_M and PITCH_LENGTH_M - low == MAX_STOP_DEPTH_M
