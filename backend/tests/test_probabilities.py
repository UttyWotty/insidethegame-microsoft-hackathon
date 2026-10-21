"""Tests for the pure probability models used by the simulator.

They verify bounds and the monotonic relationships the models are designed to encode.
Only the choose_action test uses randomness, through a seeded generator.
"""

import random

from insidegame.core.geometry import Point
from insidegame.core.zones import Channel
from insidegame.domain.teams import PlayerAttributes, TeamStyle
from insidegame.simulation.probabilities import (
    ActionKind,
    choose_action,
    effective_style,
    fatigue_factor,
    pass_success_probability,
    pressure_probability,
    scoring_probability,
    shot_probability,
    venue_factor,
)

AVERAGE = PlayerAttributes(pace=0.5, passing=0.5, finishing=0.5, tackling=0.5)
STYLE = TeamStyle(label="balanced", directness=0.5, pressing=0.5, risk=0.5, weak_flank=Channel.LEFT)
LATE_SECOND = 80 * 60
EARLY_SECOND = 10 * 60


def test_shot_probability_zero_from_own_half() -> None:
    assert shot_probability(Point(30, 34), AVERAGE, STYLE) == 0.0


def test_shot_probability_rises_closer_to_goal() -> None:
    assert shot_probability(Point(95, 34), AVERAGE, STYLE) > shot_probability(Point(80, 34), AVERAGE, STYLE)


def test_scoring_probability_prefers_central_close_positions() -> None:
    close_central = scoring_probability(Point(97, 34), 0.5)
    far_wide = scoring_probability(Point(80, 10), 0.5)
    assert 0 < far_wide < close_central < 1


def test_better_finishers_score_more() -> None:
    spot = Point(94, 34)
    assert scoring_probability(spot, 0.9) > scoring_probability(spot, 0.1)


def test_longer_and_pressured_passes_are_harder() -> None:
    short = pass_success_probability(10, 50, AVERAGE, False, 0.5, EARLY_SECOND)
    long = pass_success_probability(40, 50, AVERAGE, False, 0.5, EARLY_SECOND)
    pressured = pass_success_probability(10, 50, AVERAGE, True, 0.5, EARLY_SECOND)
    assert short > long
    assert short > pressured


def test_fatigue_reduces_late_in_match() -> None:
    assert fatigue_factor(LATE_SECOND) < fatigue_factor(EARLY_SECOND) <= 1.0


def test_high_press_engages_more_in_opponent_half() -> None:
    assert pressure_probability(10, 0.9) > pressure_probability(10, 0.1)
    assert pressure_probability(10, 0.9) > pressure_probability(90, 0.9)


def test_trailing_team_chases_late() -> None:
    chased = effective_style(STYLE, -1, LATE_SECOND)
    assert chased.risk > STYLE.risk and chased.directness > STYLE.directness


def test_leading_team_protects_late() -> None:
    protected = effective_style(STYLE, 1, LATE_SECOND)
    assert protected.risk < STYLE.risk


def test_style_unchanged_early_or_level() -> None:
    assert effective_style(STYLE, -1, EARLY_SECOND) is STYLE
    assert effective_style(STYLE, 0, LATE_SECOND) is STYLE


def test_choose_action_never_shoots_from_own_half() -> None:
    rng = random.Random(7)
    actions = {choose_action(Point(20, 34), AVERAGE, STYLE, False, rng) for _ in range(500)}
    assert ActionKind.SHOT not in actions


def test_home_sides_shoot_more_often_than_away_sides() -> None:
    near_goal = Point(92, 34)
    home = shot_probability(near_goal, AVERAGE, STYLE, venue_factor(True))
    away = shot_probability(near_goal, AVERAGE, STYLE, venue_factor(False))
    assert home > shot_probability(near_goal, AVERAGE, STYLE) > away
