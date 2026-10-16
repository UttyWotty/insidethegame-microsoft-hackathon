"""Tests for the pure instant-replay story: shot lookup, build-up selection, keyframes, flight, and shot analysis.

Events, tracking frames, and threat assessments are built by hand, so every keyframe and number can be checked exactly.
They cover tolerance matching, possession and lead filtering, ball alignment, away mirroring, and the analysis rules.
"""

import pytest

from insidegame.analytics.line_breaks import DefensiveLine, LineBreak
from insidegame.analytics.pass_quality import assess_pass
from insidegame.analytics.shot_block import BLOCK_FALLBACK_M
from insidegame.analytics.shot_card import shot_card
from insidegame.analytics.threat import ThreatAction
from insidegame.analytics.xg import expected_goals
from insidegame.core.geometry import Point, distance, mirror
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights.reel import FrameRecord
from insidegame.highlights.replay_analysis import analyse_shot
from insidegame.highlights.replay_story import (
    MIN_FLIGHT_S,
    REPLAY_MAX_ACTIONS,
    ReplayPhase,
    build_story,
    build_up_actions,
    find_shot,
    flight_seconds,
)
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import Frame

HOME, AWAY = "kba", "irv"
POSSESSION = 5
SHOT_AT = 99.0
SHOT_SPEED_KMH = 72.0
BALL_TOLERANCE_M = 0.05


@pytest.fixture(scope="module")
def metadata() -> MatchMetadata:
    return build_fixture("kestrel_bay", "ironvale", 1)


def _event(eid: str, second: float, kind: EventType, team: str, player: str, start: tuple[float, float] | None,
           end: tuple[float, float] | None = None, receiver: str | None = None, outcome: Outcome | None = Outcome.SUCCESS,
           possession: int = POSSESSION, period: int = 1, **detail: object) -> MatchEvent:
    return MatchEvent(eid, "m", 0, period, second, kind, team, player, possession,
                      Point(*start) if start else None, 0, 0, end=Point(*end) if end else None, outcome=outcome,
                      receiver_id=receiver, **detail)  # type: ignore[arg-type]


def _shot(team: str = HOME, player: str = "kba-11", result: ShotResult = ShotResult.GOAL,
          start: tuple[float, float] = (95.0, 30.0), end: tuple[float, float] = (105.0, 33.0)) -> MatchEvent:
    return _event("s", SHOT_AT, EventType.SHOT, team, player, start, end, outcome=None, shot_result=result,
                  ball_speed_kmh=SHOT_SPEED_KMH)


def _home_events() -> list[MatchEvent]:
    """A home possession: an early pass, a failed pass, pressure by the away side, then four actions to the shot."""
    return [
        _event("o1", 70.0, EventType.PASS, AWAY, "irv-04", (40.0, 30.0), (50.0, 30.0), "irv-08", possession=4),
        _event("e1", 80.0, EventType.PASS, HOME, "kba-04", (40.0, 30.0), (55.0, 30.0), "kba-08", length_m=15.0),
        _event("e2", 85.0, EventType.PASS, HOME, "kba-08", (55.0, 30.0), (60.0, 30.0), "kba-04",
               outcome=Outcome.FAILURE),
        _event("p1", 89.0, EventType.PRESSURE, AWAY, "irv-08", (50.0, 38.0)),
        _event("e3", 90.0, EventType.PASS, HOME, "kba-04", (55.0, 30.0), (70.0, 30.0), "kba-08", length_m=15.0),
        _event("e4", 92.0, EventType.CARRY, HOME, "kba-08", (70.0, 30.0), (78.0, 32.0)),
        _event("e5", 94.0, EventType.PASS, HOME, "kba-08", (78.0, 32.0), (88.0, 36.0), "kba-09", length_m=10.8),
        _event("e6", 96.0, EventType.CARRY, HOME, "kba-09", (88.0, 36.0), (92.0, 35.0)),
        _event("e7", 97.5, EventType.PASS, HOME, "kba-09", (92.0, 35.0), (95.0, 30.0), "kba-11", length_m=5.83),
        _shot(),
        _event("g", SHOT_AT, EventType.GOAL, HOME, "kba-11", (95.0, 30.0), outcome=None),
    ]


def _frame(metadata: MatchMetadata, overrides: dict[str, tuple[float, float]] | None = None) -> Frame:
    """All 22 players in two far-away rows, with overrides for named players."""
    base = [(p.player_id, 20.0, 5.0 + 3.0 * i) for i, p in enumerate(metadata.home.players)]
    base += [(p.player_id, 30.0, 5.0 + 3.0 * i) for i, p in enumerate(metadata.away.players)]
    fixed = overrides or {}
    return [(pid, *fixed[pid]) if pid in fixed else (pid, x, y) for pid, x, y in base]


def _frames(metadata: MatchMetadata, events: list[MatchEvent],
            shot_overrides: dict[str, tuple[float, float]] | None = None) -> dict[str, Frame]:
    frames = {e.event_id: _frame(metadata) for e in events}
    frames["s"] = _frame(metadata, shot_overrides)
    return frames


def _threat(event: MatchEvent, xt_start: float, xt_end: float, line_break: LineBreak | None = None) -> ThreatAction:
    assert event.team_id and event.player_id
    return ThreatAction(event.event_id, event.team_id, event.player_id, event.receiver_id, event.event_type,
                        xt_start, xt_end, line_break)


def test_find_shot_matches_within_tolerance_only_for_shots_in_the_period() -> None:
    events = _home_events()
    assert find_shot(events, 1, SHOT_AT + 0.01) == 9 and find_shot(events, 1, SHOT_AT - 0.004) == 9
    assert find_shot(events, 1, SHOT_AT + 0.02) is None
    assert find_shot(events, 2, SHOT_AT) is None
    assert find_shot(events, 1, 97.5) is None


def test_build_up_keeps_completed_team_actions_of_the_possession_capped_oldest_first() -> None:
    events = _home_events()
    actions = build_up_actions(events, 9)
    assert len(actions) == REPLAY_MAX_ACTIONS
    assert [a.event_id for a in actions] == ["e4", "e5", "e6", "e7"]


def test_build_up_drops_actions_more_than_the_lead_before_the_shot() -> None:
    events = [e for e in _home_events() if e.event_id not in {"e4", "e5", "e6", "e7"}]
    events[events.index(next(e for e in events if e.event_id == "s"))] = _shot(start=(70.0, 30.0))
    shot_index = next(i for i, e in enumerate(events) if e.event_id == "s")
    assert [a.event_id for a in build_up_actions(events, shot_index)] == ["e3"]


def test_build_up_keyframes_carry_the_ball_from_each_start_to_its_end(metadata: MatchMetadata) -> None:
    events = _home_events()
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    keyframes = story.keyframes
    actions = {e.event_id: e for e in events}
    for keyframe, action_id, following in zip(keyframes, ["e4", "e5", "e6", "e7"], keyframes[1:], strict=False):
        action = actions[action_id]
        assert keyframe.phase is ReplayPhase.BUILD_UP and action.start and action.end
        assert distance(Point(*keyframe.ball), action.start) <= BALL_TOLERANCE_M
        assert distance(Point(*following.ball), action.end) <= BALL_TOLERANCE_M
        actor = next((x, y) for pid, x, y in keyframe.positions if pid == action.player_id)
        assert actor == keyframe.ball


def test_phases_end_with_shot_then_flight_at_the_flight_time(metadata: MatchMetadata) -> None:
    events = _home_events()
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    phases = [k.phase for k in story.keyframes]
    assert phases == [ReplayPhase.BUILD_UP] * 4 + [ReplayPhase.SHOT, ReplayPhase.FLIGHT]
    shot, flight = story.keyframes[-2:]
    expected = max(distance(Point(95.0, 30.0), Point(*flight.ball)) / (SHOT_SPEED_KMH / 3.6), MIN_FLIGHT_S)
    assert shot.match_second == SHOT_AT
    assert flight.match_second == pytest.approx(SHOT_AT + expected, abs=0.01)
    assert dict((pid, (x, y)) for pid, x, y in flight.positions)["kba-11"] == (95.0, 30.0)


def test_goal_flight_ends_on_the_line_at_the_card_placement(metadata: MatchMetadata) -> None:
    events = _home_events()
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    card = story.analysis.card
    assert card.placement_y is not None
    assert story.keyframes[-1].ball == (105.0, round(34.0 + card.placement_y, 1))


def test_blocked_shot_flight_ends_at_the_shot_end(metadata: MatchMetadata) -> None:
    events = _home_events()
    events[9] = _shot(result=ShotResult.BLOCKED, end=(97.0, 31.0))
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.keyframes[-1].ball == (97.0, 31.0)


def test_blocked_shot_without_an_end_never_reaches_the_goal_line(metadata: MatchMetadata) -> None:
    """The simulator emits every blocked shot with end=None; the replay must not show the ball entering the goal."""
    events = _home_events()
    events[9] = _event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (95.0, 30.0), None, outcome=None,
                       shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.analysis.card.result == "blocked"
    assert story.keyframes[-1].ball[0] < 105.0


def test_close_range_blocked_shot_without_a_blocker_stops_short_of_the_goal_line(metadata: MatchMetadata) -> None:
    """A blocked shot from x = 103 (the simulator's carry limit) with an empty lane must not reach the goal mouth."""
    events = _home_events()
    events[9] = _event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (103.0, 34.2), None, outcome=None,
                       shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.analysis.card.result == "blocked"
    assert story.keyframes[-1].ball[0] <= 104.0


def test_blocked_shot_without_an_end_stops_at_the_blocker_in_the_lane(metadata: MatchMetadata) -> None:
    events = _home_events()
    events[9] = _event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (95.0, 34.0), None, outcome=None,
                       shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)
    blocker = metadata.away.players[4].player_id
    story = build_story(events, _frames(metadata, events, {blocker: (98.0, 34.6)}), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.keyframes[-1].ball == (98.0, 34.0)


def test_blocked_shot_without_a_blocker_stops_the_fallback_distance_out(metadata: MatchMetadata) -> None:
    events = _home_events()
    events[9] = _event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (95.0, 34.0), None, outcome=None,
                       shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)
    teammate = metadata.home.players[4].player_id
    story = build_story(events, _frames(metadata, events, {teammate: (98.0, 34.0)}), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.keyframes[-1].ball == (95.0 + BLOCK_FALLBACK_M, 34.0)


def test_away_shot_is_mirrored_into_the_absolute_frame(metadata: MatchMetadata) -> None:
    events = [_event("a1", 95.0, EventType.PASS, AWAY, "irv-08", (80.0, 40.0), (95.0, 30.0), "irv-11"),
              _shot(team=AWAY, player="irv-11")]
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    build_up, shot, flight = story.keyframes
    assert build_up.ball == (25.0, 28.0) and shot.ball == (10.0, 38.0)
    assert story.analysis.card.placement_y is not None
    expected = mirror(Point(105.0, 34.0 + story.analysis.card.placement_y))
    assert flight.ball == (round(expected.x, 1), round(expected.y, 1)) and flight.ball[0] == 0.0
    assert story.analysis.cone[0] == (10.0, 38.0) and {story.analysis.cone[1][0], story.analysis.cone[2][0]} == {0.0}


def test_no_build_up_gives_only_shot_and_flight(metadata: MatchMetadata) -> None:
    events = [_shot()]
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    assert [k.phase for k in story.keyframes] == [ReplayPhase.SHOT, ReplayPhase.FLIGHT]


def test_missing_shot_frame_or_shot_gives_no_story(metadata: MatchMetadata) -> None:
    events = _home_events()
    frames = _frames(metadata, events)
    del frames["s"]
    assert build_story(events, frames, {}, metadata, 1, SHOT_AT) is None
    assert build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT + 5) is None


def test_build_up_actions_without_a_stored_frame_are_skipped(metadata: MatchMetadata) -> None:
    events = _home_events()
    frames = _frames(metadata, events)
    del frames["e5"]
    story = build_story(events, frames, {}, metadata, 1, SHOT_AT)
    assert story is not None
    assert [k.match_second for k in story.keyframes if k.phase is ReplayPhase.BUILD_UP] == [92.0, 96.0, 97.5]


def test_flight_seconds_has_a_floor_and_a_default_speed() -> None:
    assert flight_seconds(Point(100.0, 34.0), Point(105.0, 34.0), 90.0) == MIN_FLIGHT_S
    assert flight_seconds(Point(80.0, 34.0), Point(105.0, 34.0), None) == pytest.approx(1.0)
    assert flight_seconds(Point(80.0, 34.0), Point(105.0, 34.0), 45.0) == pytest.approx(2.0)


def test_story_dict_frames_extend_the_frame_record_keys(metadata: MatchMetadata) -> None:
    events = _home_events()
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    data = story.to_dict()
    assert set(data) == {"period", "at", "frames", "analysis"}
    record_keys = set(FrameRecord(1, 0.0, "pass", None, (0.0, 0.0), []).to_dict())
    assert all(record_keys | {"phase", "receiver_id"} == set(frame) for frame in data["frames"])  # type: ignore[union-attr]


def test_analysis_card_and_goal_chance_come_from_xg_and_the_shot_card(metadata: MatchMetadata) -> None:
    events = _home_events()
    analysis = analyse_shot(events, 9, [], _frame(metadata), {}, metadata)
    xg = expected_goals(Point(95.0, 30.0), False)
    assert analysis.card.to_dict() == shot_card(events[9], xg).to_dict()
    assert analysis.xg == xg and analysis.goal_chance_pct == round(xg * 100)
    assert analysis.to_dict()["card"] == shot_card(events[9], xg).to_dict()


def test_analysis_assist_uses_the_stored_threat_and_pass_quality(metadata: MatchMetadata) -> None:
    events = _home_events()
    assist_pass = events[8]
    threat = _threat(assist_pass, 0.05, 0.12, LineBreak(3, (DefensiveLine.DEFENCE,)))
    analysis = analyse_shot(events, 9, [], _frame(metadata), {"e7": threat}, metadata)
    assist = analysis.assist
    assert assist is not None and assist.passer_id == "kba-09" and assist.length_m == 5.8
    assert assist_pass.start and assist_pass.end
    assert assist.difficulty == assess_pass(assist_pass.start, assist_pass.end, False).difficulty
    facts = threat.to_dict()
    assert assist.xt_added == facts["xt_added"] and assist.opponents_bypassed == facts["opponents_bypassed"]
    assert assist.lines_broken == facts["lines_broken"] and assist.breaks_line is True


def test_analysis_assist_threat_fields_are_empty_without_a_threat(metadata: MatchMetadata) -> None:
    analysis = analyse_shot(_home_events(), 9, [], _frame(metadata), {}, metadata)
    assert analysis.assist is not None
    assert analysis.assist.xt_added is None and analysis.assist.opponents_bypassed is None
    assert analysis.assist.lines_broken == [] and analysis.assist.breaks_line is False


def test_analysis_has_no_assist_when_the_shooter_received_no_pass(metadata: MatchMetadata) -> None:
    events = [_event("c1", 97.0, EventType.CARRY, HOME, "kba-11", (85.0, 30.0), (95.0, 30.0)), _shot()]
    analysis = analyse_shot(events, 1, [], _frame(metadata), {}, metadata)
    assert analysis.assist is None and analysis.to_dict()["assist"] is None
    assert analysis.build_up.passes == 0


def test_analysis_build_up_counts_passes_duration_and_xt(metadata: MatchMetadata) -> None:
    events = _home_events()
    threats = {e.event_id: _threat(e, 0.01, 0.03) for e in events if e.event_id in {"e1", "e3", "e4", "e7"}}
    shown = build_up_actions(events, 9)
    analysis = analyse_shot(events, 9, shown, _frame(metadata), threats, metadata)
    assert analysis.build_up.passes == 4
    assert analysis.build_up.duration_s == 19.0
    assert analysis.build_up.xt_added == pytest.approx(0.08)
    assert analysis.build_up.path == [(70.0, 30.0), (78.0, 32.0), (88.0, 36.0), (92.0, 35.0), (95.0, 30.0)]


def test_analysis_cone_counts_opponents_never_teammates(metadata: MatchMetadata) -> None:
    events = _home_events()
    shot_frame = _frame(metadata, {"irv-01": (104.0, 34.0), "irv-02": (100.0, 32.0), "kba-09": (100.0, 33.0),
                                   "kba-07": (101.0, 34.0)})
    analysis = analyse_shot(events, 9, [], shot_frame, {}, metadata)
    assert analysis.defenders_in_cone == 1 and analysis.keeper_in_cone is True
    assert analysis.cone == ((95.0, 30.0), (105.0, 30.34), (105.0, 37.66))


def test_away_close_range_blocked_shot_with_a_defender_on_top_stops_short_of_the_left_goal_line(
        metadata: MatchMetadata) -> None:
    """An away blocked shot 2 m out with the closing-down defender on the shooter still flies, and stops 1 m out."""
    events = [_event("s", SHOT_AT, EventType.SHOT, AWAY, "irv-11", (103.0, 34.2), None, outcome=None,
                     shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)]
    closer = metadata.home.players[4].player_id
    story = build_story(events, _frames(metadata, events, {closer: (1.99, 33.8)}), {}, metadata, 1, SHOT_AT)
    assert story is not None
    shot, flight = story.keyframes
    assert shot.ball == (2.0, 33.8)
    assert flight.ball[0] >= 1.0
    assert distance(Point(*shot.ball), Point(*flight.ball)) > 0.0


def test_blocked_shot_with_only_a_defender_on_top_of_the_shooter_still_leaves_the_feet(
        metadata: MatchMetadata) -> None:
    """The closing-down defender standing on the shooter is not the blocker, so the ball travels the fallback."""
    events = _home_events()
    events[9] = _event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (95.0, 34.0), None, outcome=None,
                       shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH)
    closer = metadata.away.players[4].player_id
    story = build_story(events, _frames(metadata, events, {closer: (95.02, 34.0)}), {}, metadata, 1, SHOT_AT)
    assert story is not None and story.keyframes[-1].ball == (95.0 + BLOCK_FALLBACK_M, 34.0)
