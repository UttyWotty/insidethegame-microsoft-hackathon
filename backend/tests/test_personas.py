"""Tests for persona definitions, viewer validation, and moment relevance rules.

They confirm the five personas are genuinely distinct and that relevance reflects each persona's needs.
All logic under test is pure.
"""

import pytest

from insidegame.agents.context import MomentContext
from insidegame.agents.personas import PERSONAS, PersonaKey, ViewerProfile, is_relevant
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.core.exceptions import PersonaConfigError

PERSONA_COUNT = 5


def _moment(kind: MomentKind, importance: float, team_id: str | None, players: tuple[str, ...] = ()) -> KeyMoment:
    return KeyMoment("m1", kind, 1, 600.0, importance, team_id, players)


def test_there_are_five_distinct_personas() -> None:
    assert len(PERSONAS) == PERSONA_COUNT
    for attribute in ("voice", "overlay_style", "audience", "max_words"):
        assert len({getattr(p, attribute) for p in PERSONAS.values()}) == PERSONA_COUNT


def test_superfan_requires_club_and_tracker_requires_player() -> None:
    with pytest.raises(PersonaConfigError):
        ViewerProfile("v", PersonaKey.SUPERFAN)
    with pytest.raises(PersonaConfigError):
        ViewerProfile("v", PersonaKey.PLAYER_TRACKER)


def test_goals_reach_everyone() -> None:
    goal = _moment(MomentKind.GOAL, 0.85, "irv")
    viewers = [ViewerProfile("a", PersonaKey.ANALYST), ViewerProfile("c", PersonaKey.CASUAL),
               ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id="kba"),
               ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id="kba-09"),
               ViewerProfile("n", PersonaKey.NEWCOMER)]
    assert all(is_relevant(goal, v) for v in viewers)


def test_analyst_sees_more_than_casual_fan() -> None:
    swing = _moment(MomentKind.MOMENTUM_SWING, 0.55, "irv")
    assert is_relevant(swing, ViewerProfile("a", PersonaKey.ANALYST))
    assert not is_relevant(swing, ViewerProfile("c", PersonaKey.CASUAL))


def test_superfan_ignores_rival_non_goal_moments() -> None:
    fan = ViewerProfile("s", PersonaKey.SUPERFAN, favourite_team_id="kba")
    assert not is_relevant(_moment(MomentKind.BIG_CHANCE_MISSED, 0.7, "irv"), fan)
    assert is_relevant(_moment(MomentKind.BIG_CHANCE_MISSED, 0.7, "kba"), fan)


def test_player_tracker_sees_every_moment_of_their_player() -> None:
    tracker = ViewerProfile("p", PersonaKey.PLAYER_TRACKER, favourite_player_id="kba-09")
    assert is_relevant(_moment(MomentKind.MILESTONE, 0.3, "kba", ("kba-09",)), tracker)
    assert not is_relevant(_moment(MomentKind.MILESTONE, 0.3, "kba", ("kba-10",)), tracker)


def test_goal_context_has_grounded_facts(goal_context: MomentContext) -> None:
    prompt = goal_context.to_prompt_dict()
    assert prompt["facts"]["scorer"]
    assert goal_context.home_name in str(prompt["score"])
