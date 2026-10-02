"""Integration tests for the full synthetic match simulator.

They check determinism, event stream invariants, and statistical realism across many seeds.
The simulator is pure, so these tests need no mocks or I/O.
"""

import json
from collections import Counter

import pytest

from insidegame.core.constants import PERIOD_SECONDS, PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.match import MatchResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

REALISM_SEEDS = range(30)
MATCH_SECONDS = 2 * PERIOD_SECONDS


@pytest.fixture(scope="module")
def match() -> MatchResult:
    return simulate_match(build_fixture("brookhaven", "ironvale", 42))


def test_simulation_is_deterministic(match: MatchResult) -> None:
    again = simulate_match(build_fixture("brookhaven", "ironvale", 42))
    assert again.events == match.events


def test_sequence_is_global_and_clock_monotonic_within_period(match: MatchResult) -> None:
    assert [e.sequence for e in match.events] == list(range(len(match.events)))
    for period in (1, 2):
        seconds = [e.match_second for e in match.events if e.period == period]
        assert seconds == sorted(seconds)
        assert seconds[0] == (period - 1) * PERIOD_SECONDS


def test_match_has_two_periods_with_stoppage(match: MatchResult) -> None:
    counts = Counter(e.event_type for e in match.events)
    assert counts[EventType.PERIOD_START] == 2
    assert counts[EventType.PERIOD_END] == 2
    assert match.events[-1].match_second >= MATCH_SECONDS


def test_goal_events_match_final_score(match: MatchResult) -> None:
    goals = [e for e in match.events if e.event_type is EventType.GOAL]
    assert len(goals) == match.home_goals + match.away_goals
    last = match.events[-1]
    assert (last.score_home, last.score_away) == (match.home_goals, match.away_goals)


def test_every_goal_follows_a_scoring_shot(match: MatchResult) -> None:
    for event in match.events:
        if event.event_type is EventType.GOAL:
            shot = match.events[event.sequence - 1]
            assert shot.event_type is EventType.SHOT and shot.shot_result is ShotResult.GOAL


def test_coordinates_stay_on_pitch(match: MatchResult) -> None:
    for event in match.events:
        for point in (event.start, event.end):
            if point is not None:
                assert 0 <= point.x <= PITCH_LENGTH_M and 0 <= point.y <= PITCH_WIDTH_M


def test_events_serialise_to_json(match: MatchResult) -> None:
    payload = json.dumps([e.to_dict() for e in match.events])
    assert json.loads(payload)[0]["event_type"] == EventType.PERIOD_START.value


def test_statistics_are_football_realistic() -> None:
    shots = goals = passes = completed = 0
    for seed in REALISM_SEEDS:
        result = simulate_match(build_fixture("kestrel_bay", "silverlake", seed))
        goals += result.home_goals + result.away_goals
        for e in result.events:
            shots += e.event_type is EventType.SHOT
            if e.event_type is EventType.PASS:
                passes += 1
                completed += e.outcome is Outcome.SUCCESS
    n = len(REALISM_SEEDS)
    assert 15 <= shots / n <= 35
    assert 1.5 <= goals / n <= 4.5
    assert 700 <= passes / n <= 1300
    assert 0.72 <= completed / passes <= 0.88
