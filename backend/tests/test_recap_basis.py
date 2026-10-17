"""Tests for the shared recap vocabulary that sits below both the agents and highlights layers.

They pin RecapStage's values, the turning-point importance threshold, and moment_actor's fact-key priority.
The agents and highlights modules must both see the same objects, so a moved constant cannot drift between layers.
"""

from insidegame.agents import recap_context
from insidegame.analytics.recap_basis import MIN_TURNING_POINT_IMPORTANCE, RecapStage, moment_actor
from insidegame.highlights import reel

EXPECTED_THRESHOLD = 0.45


def test_recap_stage_values_are_stable() -> None:
    assert [s.value for s in RecapStage] == ["half_time", "full_time"]


def test_turning_point_threshold_is_unchanged_and_shared() -> None:
    assert MIN_TURNING_POINT_IMPORTANCE == EXPECTED_THRESHOLD
    assert recap_context.MIN_TURNING_POINT_IMPORTANCE is reel.MIN_TURNING_POINT_IMPORTANCE
    assert recap_context.RecapStage is reel.RecapStage is RecapStage


def test_moment_actor_prefers_scorer_then_player_then_goalkeeper_then_passer() -> None:
    assert moment_actor({"passer": "P", "goalkeeper": "G", "player": "L", "scorer": "S"}) == "S"
    assert moment_actor({"passer": "P", "goalkeeper": "G", "player": "L"}) == "L"
    assert moment_actor({"passer": "P", "goalkeeper": "G"}) == "G"
    assert moment_actor({"passer": "P"}) == "P"


def test_moment_actor_skips_empty_values_and_returns_none_without_a_player() -> None:
    assert moment_actor({}) is None
    assert moment_actor({"scorer": "", "passer": "P"}) == "P"
    assert moment_actor({"scorer": None, "xg": 0.3}) is None
