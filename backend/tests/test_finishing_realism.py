"""Permanent realism checks on simulated finishing: no walk-in goals, a realistic goal mix by distance, a set keeper.

Events-only matches for seeds 1-60 of the demo fixture check the carry stop bound, the share of shots and goals
from 2.5 m or less off the goal line, and goal and shot shares by distance from the goal centre.
Tracked matches for seeds 1-20 read each defending keeper from the tracking model before the shot, as the live
service feeds the analyzer, and check that the keeper stands nearer the goal line than a close shooter.
"""

import pytest

from insidegame.core.geometry import distance_to_goal, mirror
from insidegame.domain.enums import EventType, ShotResult, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.open_play import CARRY_STOP_X_M
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, TrackingModel

EVENT_SEEDS = range(1, 61)
TRACKED_SEEDS = range(1, 21)
WALK_IN_X_M = 102.5
MAX_WALK_IN_SHOT_SHARE = 0.01
MAX_WALK_IN_GOAL_SHARE = 0.02
CLOSE_RANGE_M = 6.0
MID_RANGE_M = 18.0
MAX_CLOSE_GOAL_SHARE = 0.25
MAX_CLOSE_SHOT_SHARE = 0.08
MIN_MID_GOAL_SHARE = 0.60
KEEPER_CHECK_RANGE_M = 20.0
MIN_KEEPER_SET_SHARE = 0.98


@pytest.fixture(scope="module")
def matches() -> list[MatchResult]:
    return [simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, seed)) for seed in EVENT_SEEDS]


@pytest.fixture(scope="module")
def shots(matches: list[MatchResult]) -> list[MatchEvent]:
    return [e for m in matches for e in m.events if e.event_type is EventType.SHOT and e.start is not None]


def _goals(shots: list[MatchEvent]) -> list[MatchEvent]:
    return [s for s in shots if s.shot_result is ShotResult.GOAL]


def test_carries_never_end_beyond_the_stop_band_unless_they_start_there(matches: list[MatchResult]) -> None:
    carries = [e for m in matches for e in m.events if e.event_type is EventType.CARRY and e.end is not None]
    assert carries
    assert all(c.end.x <= max(CARRY_STOP_X_M[1], c.start.x) for c in carries)


def test_walk_in_shots_and_goals_are_rare(shots: list[MatchEvent]) -> None:
    goals = _goals(shots)
    walk_in_shots = [s for s in shots if s.start.x >= WALK_IN_X_M]
    walk_in_goals = [g for g in goals if g.start.x >= WALK_IN_X_M]
    assert len(walk_in_shots) / len(shots) <= MAX_WALK_IN_SHOT_SHARE
    assert len(walk_in_goals) / len(goals) <= MAX_WALK_IN_GOAL_SHARE


def test_goals_come_mostly_from_six_to_eighteen_metres(shots: list[MatchEvent]) -> None:
    goals = _goals(shots)
    close_shots = [s for s in shots if distance_to_goal(s.start) < CLOSE_RANGE_M]
    close_goals = [g for g in goals if distance_to_goal(g.start) < CLOSE_RANGE_M]
    mid_goals = [g for g in goals if CLOSE_RANGE_M <= distance_to_goal(g.start) < MID_RANGE_M]
    assert len(close_goals) / len(goals) <= MAX_CLOSE_GOAL_SHARE
    assert len(close_shots) / len(shots) <= MAX_CLOSE_SHOT_SHARE
    assert len(mid_goals) / len(goals) >= MIN_MID_GOAL_SHARE


def _keeper_set_on_close_shots(result: MatchResult) -> tuple[int, int]:
    """(shots within range with the keeper strictly nearer the goal line than the shooter, shots within range)."""
    tracking = TrackingModel(result.metadata)
    set_count = total = 0
    for index, event in enumerate(result.events):
        if (event.event_type is EventType.SHOT and event.start is not None and event.team_id is not None
                and tracking.previous and distance_to_goal(event.start) <= KEEPER_CHECK_RANGE_M):
            side = result.metadata.side_of(event.team_id)
            keeper_id = result.metadata.team(side.opponent).goalkeeper().player_id
            keeper = tracking.previous[keeper_id]
            keeper_attacking_frame = keeper if side is Side.HOME else mirror(keeper)
            total += 1
            set_count += keeper_attacking_frame.x > event.start.x
        tracking.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
    return set_count, total


def test_the_keeper_stands_between_a_close_shooter_and_the_goal_line() -> None:
    counts = [_keeper_set_on_close_shots(simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, seed)))
              for seed in TRACKED_SEEDS]
    set_count, total = sum(c[0] for c in counts), sum(c[1] for c in counts)
    assert total and set_count / total >= MIN_KEEPER_SET_SHARE


OTHER_FIXTURES = (("brookhaven", "silverlake"), ("ironvale", "kestrel_bay"))


@pytest.mark.parametrize("home, away", OTHER_FIXTURES)
def test_walk_ins_are_rare_for_other_fixtures_and_the_away_side(home: str, away: str) -> None:
    results = [simulate_match(build_fixture(home, away, seed)) for seed in EVENT_SEEDS]
    shots = [e for m in results for e in m.events if e.event_type is EventType.SHOT and e.start is not None]
    goals = _goals(shots)
    assert {m.metadata.side_of(s.team_id) for m in results for s in m.events
            if s.event_type is EventType.SHOT and s.start is not None} == {Side.HOME, Side.AWAY}
    assert len([s for s in shots if s.start.x >= WALK_IN_X_M]) / len(shots) <= MAX_WALK_IN_SHOT_SHARE
    assert len([g for g in goals if g.start.x >= WALK_IN_X_M]) / len(goals) <= MAX_WALK_IN_GOAL_SHARE
    assert all(c.end.x <= max(CARRY_STOP_X_M[1], c.start.x) for m in results for c in m.events
               if c.event_type is EventType.CARRY and c.end is not None)
