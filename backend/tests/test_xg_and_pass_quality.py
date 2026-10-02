"""Tests for the expected goals model and the pass difficulty rating.

They verify bounds, monotonic behaviour, and that difficulty factors are reported correctly.
Both models are pure functions of geometry and pressure.
"""

from insidegame.analytics.pass_quality import assess_pass
from insidegame.analytics.xg import expected_goals
from insidegame.core.geometry import Point

CENTRAL_Y = 34.0


def test_xg_is_a_probability() -> None:
    for x in (60, 85, 95, 103):
        assert 0.0 < expected_goals(Point(x, CENTRAL_Y), False) < 1.0


def test_xg_higher_closer_and_more_central() -> None:
    assert expected_goals(Point(98, CENTRAL_Y), False) > expected_goals(Point(85, CENTRAL_Y), False)
    assert expected_goals(Point(95, CENTRAL_Y), False) > expected_goals(Point(95, 8), False)


def test_xg_lower_under_pressure() -> None:
    spot = Point(94, CENTRAL_Y)
    assert expected_goals(spot, True) < expected_goals(spot, False)


def test_short_square_pass_is_easy() -> None:
    quality = assess_pass(Point(40, 30), Point(42, 36), False)
    assert quality.difficulty < 10
    assert not quality.progressive and not quality.final_third_entry


def test_long_pressured_progressive_pass_into_final_third_is_hard() -> None:
    quality = assess_pass(Point(40, 10), Point(80, 50), True)
    assert quality.difficulty >= 80
    assert quality.progressive and quality.final_third_entry
    assert quality.pressure_factor == 1.0 and quality.switch_factor == 1.0


def test_difficulty_is_bounded() -> None:
    quality = assess_pass(Point(1, 1), Point(103, 67), True)
    assert 0 <= quality.difficulty <= 100
