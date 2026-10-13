"""Tests for the live win probability model.

They check that kick-off odds match typical top-flight results, that goals and the clock move them sensibly, and
that a finished match is certain. All logic is pure.
"""

from insidegame.analytics.win_probability import MATCH_SECONDS, win_probability


def test_kick_off_odds_match_typical_results_with_home_advantage() -> None:
    p = win_probability(0, 0, 0.0, 0.0, 0.0, finished=False)
    assert 0.40 <= p.home <= 0.50 and 0.22 <= p.draw <= 0.32 and 0.25 <= p.away <= 0.35
    assert abs(p.home + p.draw + p.away - 1.0) < 0.002


def test_goals_and_time_move_the_odds() -> None:
    early = win_probability(1, 0, 0.5, 0.2, 600.0, finished=False)
    late = win_probability(1, 0, 1.0, 0.4, MATCH_SECONDS - 300.0, finished=False)
    assert late.home > early.home > 0.5 and late.away < early.away
    pressing = win_probability(0, 0, 0.2, 1.8, 3600.0, finished=False)
    assert pressing.away > pressing.home


def test_a_finished_match_is_certain() -> None:
    assert win_probability(2, 2, 1.0, 1.0, MATCH_SECONDS, finished=True).to_dict() == {"home": 0.0, "draw": 1.0, "away": 0.0}
