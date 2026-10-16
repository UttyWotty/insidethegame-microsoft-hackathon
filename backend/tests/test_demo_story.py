"""Tests for the demo-story scorer and the auto-replay queue rules it mirrors from the frontend.

A hand-built match passes all eight hard rules; each rule is then broken on its own and must reject the story, and
the preference weights must add up. played_replays queues a replay due while another rolls, caps the queue with goal
priority, drops stale queued replays, and follows the stream clock across the half-time break.
An integration test checks that the demo seed passes and names the minutes docs/DEMO_SCRIPT.md quotes.
"""

import re
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.core.geometry import Point
from insidegame.datasets.demo_search import story_for_seed
from insidegame.datasets.demo_story import (
    DEMO_SPEED,
    HALF_TIME_BREAK_MATCH_S,
    REPLAY_DELAY_S,
    REPLAY_MAX_LAG_MATCH_S,
    REPLAY_QUEUE_MAX,
    REPLAY_ROLL_S,
    DemoStory,
    ReplayCandidate,
    StoryCriteria,
    played_replays,
    score_story,
    stream_times,
)
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.live.pacing import HALF_TIME_BREAK_MATCH_S as LIVE_HALF_TIME_BREAK_MATCH_S
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED, build_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SCRIPT = REPO_ROOT / "docs" / "DEMO_SCRIPT.md"
CRITERIA = StoryCriteria()
METADATA: MatchMetadata = build_fixture(DEMO_HOME, DEMO_AWAY, 1)
HOME, AWAY = METADATA.home.team_id, METADATA.away.team_id
EXPLOITED = "left"
FLAG_ID, GOAL_ID, SHIFT_ID = "m-flag", "m-goal", "m-shift"
SAVE_SPOT = Point(100.0, 34.0)
FAR_SPOT = Point(70.0, 34.0)
GOAL_SPOT = Point(95.0, 34.0)
BASE_SCORE = 7
SHOT_SPACING_S = 10.0


@dataclass(frozen=True)
class Scenario:
    """Knobs of the hand-built match; the defaults pass every hard rule."""

    flags: int = 1
    flag_team: str = HOME
    flag_channel: str = EXPLOITED
    flag_second: float = 2700.0
    goal_team: str = HOME
    goal_state: str = "go_ahead"
    goal_second: float = 3100.0
    goal_distance_m: float = 10.0
    shift_team: str = HOME
    shift_trigger: str = "went_ahead"
    shift_second: float = 3700.0
    control_after_pct: float = 40.0
    save_spot: Point = SAVE_SPOT
    pass_outcome: Outcome = Outcome.SUCCESS
    chances_before_goal: int = 0
    chance_lead_s: float = 1.0
    play_on_s: float = 0.0
    comeback: bool = False


def _event(event_id: str, sequence: int, period: int, second: float, kind: EventType, team: str, start: Point,
           possession: int, score: tuple[int, int], **detail: object) -> MatchEvent:
    return MatchEvent(event_id, METADATA.match_id, sequence, period, second, kind, team, f"{team}-09", possession,
                      start, score[0], score[1], **detail)


def _events(s: Scenario) -> list[MatchEvent]:
    events = [_event("e-save", 1, 1, 1200.0, EventType.SHOT, AWAY, s.save_spot, 1, (0, 0),
                     shot_result=ShotResult.SAVED)]
    if s.comeback:
        events += [_event("e-early", 2, 1, 1500.0, EventType.SHOT, AWAY, GOAL_SPOT, 2, (0, 1),
                          shot_result=ShotResult.GOAL),
                   _event("e-level", 3, 1, 1800.0, EventType.SHOT, HOME, GOAL_SPOT, 3, (1, 1),
                          shot_result=ShotResult.GOAL)]
    score = (2, 1) if s.comeback else (1, 0)
    before = (score[0] - 1, score[1])
    start = s.goal_second - 3 * SHOT_SPACING_S
    events += [_event(f"e-pass{i}", 3 + i, 2, start + i * SHOT_SPACING_S, EventType.PASS, s.goal_team, GOAL_SPOT, 5,
                      before, outcome=s.pass_outcome) for i in range(2)]
    n = s.chances_before_goal
    events += [_event(f"e-chance{i}", 5, 2, s.goal_second - s.chance_lead_s * (n - i), EventType.SHOT, s.goal_team,
                      SAVE_SPOT, 5, before, shot_result=ShotResult.OFF_TARGET) for i in range(n)]
    events.append(_event("e-goal", 6, 2, s.goal_second, EventType.SHOT, s.goal_team, GOAL_SPOT, 5, score,
                         shot_result=ShotResult.GOAL))
    # Play goes on after the goal (a pass every SHOT_SPACING_S) so the live clock moves and queued replays age.
    events += [_event(f"e-on{i}", 7 + i, 2, s.goal_second + (i + 1) * SHOT_SPACING_S, EventType.PASS, AWAY, FAR_SPOT,
                      9, score, outcome=Outcome.SUCCESS) for i in range(int(s.play_on_s // SHOT_SPACING_S))]
    return events


def _plain_goal(moment_id: str, second: float, team: str, event_id: str, score: tuple[int, int],
                state: str) -> KeyMoment:
    return KeyMoment(moment_id, MomentKind.GOAL, 1, second, 1.0, team, event_ids=(event_id,),
                     facts={"scorer": "Other", "score_home": score[0], "score_away": score[1], "xg": 0.125,
                            "distance_m": 10.0, "game_state_change": state})


def _moments(s: Scenario) -> list[KeyMoment]:
    flags = [KeyMoment(f"{FLAG_ID}{i}" if i else FLAG_ID, MomentKind.TACTICAL_PATTERN, 2, s.flag_second - i, 0.5,
                       s.flag_team, facts={"pattern": "flank_exposed", "channel": s.flag_channel,
                                           "summary": "Down the left"}) for i in range(s.flags)]
    score = (2, 1) if s.comeback else (1, 0)
    goals = [KeyMoment(GOAL_ID, MomentKind.GOAL, 2, s.goal_second, 1.0, s.goal_team, event_ids=("e-goal",),
                       facts={"scorer": "Nine", "score_home": score[0], "score_away": score[1], "xg": 0.125,
                              "distance_m": s.goal_distance_m, "game_state_change": s.goal_state,
                              "flagged_moment_id": FLAG_ID})]
    if s.comeback:
        goals[:0] = [_plain_goal("m-early", 1500.0, AWAY, "e-early", (0, 1), "opener"),
                     _plain_goal("m-level", 1800.0, HOME, "e-level", (1, 1), "equaliser")]
    shift = KeyMoment(SHIFT_ID, MomentKind.SHAPE_SHIFT, 2, s.shift_second, 0.6, s.shift_team,
                      facts={"direction": "dropped", "goal_difference": 1, "trigger": s.shift_trigger,
                             "control_before_pct": 50.0, "control_after_pct": s.control_after_pct,
                             "line_before_m": 30.0, "line_after_m": 20.0})
    return sorted(flags + goals + [shift], key=lambda m: m.match_second)


def _score(s: Scenario) -> DemoStory | None:
    return score_story(1, METADATA, _events(s), _moments(s), CRITERIA)


def test_the_hand_built_match_passes_with_every_base_preference() -> None:
    story = _score(Scenario())
    assert story is not None
    assert (story.arc_minute, story.flag_minute, story.shift_minute) == ("52'", "46'", "62'")
    assert story.winner and story.exploited_flank and story.save_replay_plays and not story.late
    assert story.arc_build_up_passes == 2 and story.lead_minutes == 6.7 and story.score == BASE_SCORE


@pytest.mark.parametrize("broken", [
    pytest.param(Scenario(flags=CRITERIA.max_flags + 1), id="1-too-many-flags"),
    pytest.param(Scenario(goal_state="extends_lead"), id="2-no-flagged-go-ahead-goal"),
    pytest.param(Scenario(goal_team=AWAY), id="2-arc-goal-not-home"),
    pytest.param(Scenario(flag_team=AWAY), id="3-flag-not-home"),
    pytest.param(Scenario(flag_channel="centre"), id="3-flag-not-on-a-flank"),
    pytest.param(Scenario(flag_second=3000.0), id="3-lead-too-short"),
    pytest.param(Scenario(flag_second=2000.0), id="3-lead-too-long"),
    pytest.param(Scenario(goal_distance_m=5.0), id="4-tap-in"),
    pytest.param(Scenario(shift_team=AWAY), id="5-shift-not-home"),
    pytest.param(Scenario(shift_trigger="momentum"), id="5-shift-not-after-going-ahead"),
    pytest.param(Scenario(shift_second=3000.0), id="5-shift-before-the-goal"),
    pytest.param(Scenario(control_after_pct=55.0), id="5-control-rose"),
    pytest.param(Scenario(save_spot=FAR_SPOT), id="6-no-big-save"),
    pytest.param(Scenario(pass_outcome=Outcome.FAILURE), id="7-no-build-up"),
    pytest.param(Scenario(chances_before_goal=1, play_on_s=1200.0), id="8-arc-replay-stale-in-the-queue"),
])
def test_each_hard_rule_rejects_on_its_own(broken: Scenario) -> None:
    assert _score(broken) is None


def test_preference_weights_add_up() -> None:
    late = Scenario(flag_second=4000.0, goal_second=4400.0, shift_second=4900.0)
    late_story = _score(late)
    assert late_story is not None and late_story.late and late_story.score == BASE_SCORE + 2
    both = _score(replace(late, comeback=True))
    assert both is not None and both.comeback and both.late and both.score == BASE_SCORE + 4
    slow = _score(Scenario(flag_second=2400.0))
    assert slow is not None and slow.lead_minutes == 11.7 and slow.score == BASE_SCORE - 1
    right = _score(Scenario(flag_channel="right"))
    assert right is not None and not right.exploited_flank and right.score == BASE_SCORE - 1


def test_comeback_counts_when_home_trailed_before_the_arc_goal() -> None:
    story = _score(Scenario(comeback=True))
    assert story is not None and story.comeback and story.winner and story.score == BASE_SCORE + 2
    assert story.goal_minutes == ("26'", "31'", "52'") and (story.home_goals, story.away_goals) == (2, 1)


def test_a_later_equaliser_cancels_the_winner_preference() -> None:
    events = _events(Scenario())
    events.append(_event("e-late", 7, 2, 3500.0, EventType.SHOT, AWAY, GOAL_SPOT, 6, (1, 1),
                         shot_result=ShotResult.GOAL))
    moments = sorted(_moments(Scenario()) + [replace(_plain_goal("m-late", 3500.0, AWAY, "e-late", (1, 1),
                                                                 "equaliser"), period=2)],
                     key=lambda m: m.match_second)
    story = score_story(1, METADATA, events, moments, CRITERIA)
    assert story is not None and not story.winner and story.score == BASE_SCORE - 3


def test_a_chance_just_before_the_arc_goal_only_queues_its_replay() -> None:
    """The old drop rule rejected this match; with no play after the goal the queued goal replay is never stale."""
    assert _score(Scenario(chances_before_goal=1)) is not None


ROLL = REPLAY_ROLL_S * DEMO_SPEED


def _plays(shots: list[tuple[float, bool]], clock_until: float = 6000.0) -> list[bool]:
    """Run the queue model on (match second, goal) shots in one period, with a live clock ticking every second."""
    clock = [(float(t), float(t)) for t in range(int(clock_until))]
    candidates = [ReplayCandidate(second, second, goal) for second, goal in shots]
    return played_replays(candidates, clock, DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S)


def test_a_replay_due_while_another_rolls_is_queued_and_plays_after_it() -> None:
    assert _plays([(100.0, False), (130.0, True)]) == [True, True]
    assert _plays([(100.0, False), (100.0 + ROLL, False)]) == [True, True]
    assert _plays([]) == []


def test_the_queue_is_capped_and_a_goal_replaces_the_oldest_non_goal() -> None:
    assert REPLAY_QUEUE_MAX == 2 and REPLAY_MAX_LAG_MATCH_S == 600.0
    clock = [(0.0, 0.0)]
    shots = [ReplayCandidate(s, s, g) for s, g in [(100.0, False), (101.0, False), (102.0, False), (103.0, True)]]
    assert played_replays(shots, clock, DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S) == [True, False, True, True]
    misses = [ReplayCandidate(s, s, False) for s in (100.0, 101.0, 102.0, 103.0)]
    assert played_replays(misses, clock, DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S) == [True, True, True, False]


def test_a_queued_replay_more_than_ten_minutes_behind_live_is_dropped_goals_included() -> None:
    assert _plays([(100.0, False), (130.0, False), (140.0, True)]) == [True, True, False]
    assert _plays([(100.0, True), (130.0, True), (140.0, False)]) == [True, True, False]
    assert _plays([(100.0, False), (101.0, True)]) == [True, False]


def test_a_queued_replay_exactly_ten_minutes_behind_live_still_plays() -> None:
    """The lag rule is inclusive: at exactly REPLAY_MAX_LAG_MATCH_S behind live it plays, half a second more drops it."""
    finish = REPLAY_DELAY_S * DEMO_SPEED + ROLL
    on_boundary = finish - REPLAY_MAX_LAG_MATCH_S
    for goal in (False, True):
        assert _plays([(0.0, False), (on_boundary, goal)]) == [True, True]
        assert _plays([(0.0, False), (on_boundary - 0.5, goal)]) == [True, False]


def test_stream_times_add_the_live_half_time_break() -> None:
    assert HALF_TIME_BREAK_MATCH_S == LIVE_HALF_TIME_BREAK_MATCH_S
    assert stream_times([(1, 10.0), (1, 40.0), (1, 30.0), (2, 2700.0), (2, 2710.0)]) == [
        0.0, 30.0, 30.0, 30.0 + HALF_TIME_BREAK_MATCH_S, 40.0 + HALF_TIME_BREAK_MATCH_S]
    assert stream_times([]) == []


def test_a_first_half_replay_queued_over_the_break_plays_in_the_second_half() -> None:
    events = [(1, 2690.0), (1, 2700.0), (2, 2700.0), (2, 3300.0)]
    times = stream_times(events)
    clock = [(t, second) for t, (_, second) in zip(times, events, strict=True)]
    shots = [ReplayCandidate(times[0], 2690.0, False), ReplayCandidate(times[1], 2700.0, True)]
    assert played_replays(shots, clock, DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S) == [True, True]


def _script_minute(pattern: str) -> str:
    found = re.search(pattern, DEMO_SCRIPT.read_text(encoding="utf-8"))
    assert found is not None, pattern
    return found.group(1)


def test_the_demo_seed_tells_the_story_the_script_names() -> None:
    story = story_for_seed(DEMO_SEED, CRITERIA)
    assert story is not None
    assert story.arc_minute == _script_minute(r"At (\d+') \w+ \w+ scores")
    assert story.flag_minute == _script_minute(r"Scout flagged (\d+'):")
    assert story.shift_minute == _script_minute(r"Shape shift at (\d+')")
