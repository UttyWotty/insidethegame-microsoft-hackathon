"""Tests for the pure instant-replay story: shot lookup, build-up selection, keyframes, flight, and shot analysis.

Events, tracking frames, and threat assessments are built by hand, so every keyframe and number can be checked exactly.
They cover tolerance matching, possession and lead filtering, ball alignment, away mirroring, saved shots stopping at
the keeper (non-saved flights unchanged), and the analysis rules.
"""

import pytest

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.line_breaks import DefensiveLine, LineBreak
from insidegame.analytics.pass_quality import assess_pass
from insidegame.analytics.shot_block import BLOCK_FALLBACK_M
from insidegame.analytics.shot_card import shot_card
from insidegame.analytics.shot_save import SAVE_MAX_DEPTH_M, SAVE_MIN_DEPTH_M
from insidegame.analytics.threat import ThreatAction
from insidegame.analytics.xg import expected_goals
from insidegame.core.constants import PITCH_LENGTH_M
from insidegame.core.geometry import Point, distance, mirror
from insidegame.domain.enums import EventType, Outcome, Position, ShotResult, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.highlights.reel import FrameRecord
from insidegame.highlights.replay_analysis import analyse_shot
from insidegame.highlights.replay_story import (
    DEFAULT_PASS_SPEED_KMH,
    MIN_FLIGHT_S,
    RECEPTION_EVENT,
    RECEPTION_MAX_SHARE,
    REPLAY_MAX_ACTIONS,
    ReplayPhase,
    ReplayStory,
    build_story,
    build_up_actions,
    find_shot,
    flight_seconds,
    reception_keyframe,
)
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, Frame, TrackingModel

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
    starts = [i for i, k in enumerate(keyframes) if k.phase is ReplayPhase.BUILD_UP and k.event_type != RECEPTION_EVENT]
    for index, action_id in zip(starts, ["e4", "e5", "e6", "e7"], strict=True):
        keyframe, following, action = keyframes[index], keyframes[index + 1], actions[action_id]
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
    assert phases == [ReplayPhase.BUILD_UP] * 6 + [ReplayPhase.SHOT, ReplayPhase.FLIGHT]
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
    build_up, reception, shot, flight = story.keyframes
    assert build_up.ball == (25.0, 28.0) and reception.ball == shot.ball == (10.0, 38.0)
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
    seconds = [k.match_second for k in story.keyframes if k.phase is ReplayPhase.BUILD_UP]
    assert seconds == pytest.approx([92.0, 96.0, 97.5, 97.5 + MIN_FLIGHT_S])


def test_a_completed_pass_reaches_its_receiver_at_the_pass_speed(metadata: MatchMetadata) -> None:
    events = _home_events()
    story = build_story(events, _frames(metadata, events), {}, metadata, 1, SHOT_AT)
    assert story is not None
    receptions = [k for k in story.keyframes if k.event_type == RECEPTION_EVENT]
    assert [k.player_id for k in receptions] == ["kba-09", "kba-11"]
    first = receptions[0]
    assert first.ball == (88.0, 36.0) and first.positions[[p for p, _, _ in first.positions].index("kba-09")][1:] == (88.0, 36.0)
    assert first.match_second == pytest.approx(94.0 + 10.77 / (DEFAULT_PASS_SPEED_KMH / 3.6), abs=0.01)


def test_a_reception_lands_before_the_next_action_and_only_for_completed_passes(metadata: MatchMetadata) -> None:
    long_pass = _event("lp", 90.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (80.0, 30.0), "kba-08",
                       ball_speed_kmh=36.0)
    frame = _frame(metadata)
    reception = reception_keyframe(long_pass, frame, HOME, metadata, 91.0)
    assert reception is not None and reception.match_second == pytest.approx(90.0 + RECEPTION_MAX_SHARE)
    failed = _event("fp", 90.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (40.0, 30.0), "kba-08",
                    outcome=Outcome.FAILURE)
    carry = _event("c", 90.0, EventType.CARRY, HOME, "kba-04", (20.0, 30.0), (40.0, 30.0))
    assert reception_keyframe(failed, frame, HOME, metadata, 95.0) is None
    assert reception_keyframe(carry, frame, HOME, metadata, 95.0) is None
    assert reception_keyframe(long_pass, frame, HOME, metadata, 90.0) is None


def test_the_strike_shows_the_stored_frame_after_smoothing(metadata: MatchMetadata) -> None:
    events = _home_events()
    frames = _frames(metadata, events, {"irv-01": (100.0, 34.0)})
    story = build_story(events, frames, {}, metadata, 1, SHOT_AT)
    assert story is not None
    shot = next(k for k in story.keyframes if k.phase is ReplayPhase.SHOT)
    assert dict((p, (x, y)) for p, x, y in shot.positions)["irv-01"] == (100.0, 34.0)


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


def _keeper(team: Team) -> str:
    """The team's goalkeeper player id."""
    return next(p.player_id for p in team.players if p.position is Position.GOALKEEPER)


def _positions(frame: Frame) -> dict[str, tuple[float, float]]:
    """Each player's (x, y) in a frame, by player id."""
    return {pid: (x, y) for pid, x, y in frame}


SAVE_KEEPER_SPOT = (103.5, 34.0)
SAVE_BLOCKER_SPOT = (98.0, 34.6)


def _story_with_keeper(metadata: MatchMetadata, shot: MatchEvent) -> ReplayStory:
    """A home possession ending in shot, with the away keeper 1.5 m off the line and a defender in the lane."""
    events = _home_events()
    events[9] = shot
    overrides = {_keeper(metadata.away): SAVE_KEEPER_SPOT,
                 metadata.away.players[4].player_id: SAVE_BLOCKER_SPOT}
    story = build_story(events, _frames(metadata, events, overrides), {}, metadata, 1, SHOT_AT)
    assert story is not None
    return story


def test_saved_shot_stops_short_of_the_line_at_the_keeper_who_moves_onto_the_save(metadata: MatchMetadata) -> None:
    story = _story_with_keeper(metadata, _shot(result=ShotResult.SAVED))
    shot, flight = story.keyframes[-2:]
    assert story.analysis.card.result == "saved" and story.analysis.card.placement_y == -1.63
    assert flight.ball == (103.5, 32.0)
    assert flight.ball[0] <= 105.0 - SAVE_MIN_DEPTH_M
    assert _positions(flight.positions)[_keeper(metadata.away)] == flight.ball
    assert _positions(shot.positions)[_keeper(metadata.away)] == SAVE_KEEPER_SPOT
    assert _positions(flight.positions)["kba-11"] == shot.ball
    moved = {pid for pid, spot in _positions(flight.positions).items() if _positions(shot.positions)[pid] != spot}
    assert moved == {_keeper(metadata.away)}
    expected = max(distance(Point(95.0, 30.0), Point(103.5, 32.0)) / (SHOT_SPEED_KMH / 3.6), MIN_FLIGHT_S)
    assert flight.match_second == pytest.approx(SHOT_AT + expected, abs=0.01)


def test_away_saved_shot_stops_short_of_the_left_goal_line_at_the_home_keeper(metadata: MatchMetadata) -> None:
    events = [_shot(team=AWAY, player="irv-11", result=ShotResult.SAVED)]
    keeper = _keeper(metadata.home)
    story = build_story(events, _frames(metadata, events, {keeper: (1.5, 34.0)}), {}, metadata, 1, SHOT_AT)
    assert story is not None
    flight = story.keyframes[-1]
    assert SAVE_MIN_DEPTH_M <= flight.ball[0] == 1.5
    assert _positions(flight.positions)[keeper] == flight.ball


def test_saved_shot_without_the_keeper_in_the_frame_stops_the_default_depth_out(metadata: MatchMetadata) -> None:
    events = [_shot(result=ShotResult.SAVED)]
    keeper = _keeper(metadata.away)
    frames = {"s": [row for row in _frame(metadata) if row[0] != keeper]}
    story = build_story(events, frames, {}, metadata, 1, SHOT_AT)
    assert story is not None
    shot, flight = story.keyframes
    assert flight.ball[0] == 104.0 and flight.positions == shot.positions


@pytest.mark.parametrize(("shot", "ball", "arrival"), [
    (_shot(), (105.0, 34.3), 99.5442655601818),
    (_shot(result=ShotResult.OFF_TARGET, end=(105.0, 42.0)), (105.0, 36.9), 99.60634066332385),
    (_event("s", SHOT_AT, EventType.SHOT, HOME, "kba-11", (95.0, 34.0), None, outcome=None,
            shot_result=ShotResult.BLOCKED, ball_speed_kmh=SHOT_SPEED_KMH), (98.0, 34.0), 99.4),
], ids=["goal", "off_target", "blocked"])
def test_goal_off_target_and_blocked_flights_are_unchanged(metadata: MatchMetadata, shot: MatchEvent,
                                                           ball: tuple[float, float], arrival: float) -> None:
    """The FLIGHT keyframe of every non-saved shot equals the values recorded before saves stopped at the keeper."""
    story = _story_with_keeper(metadata, shot)
    strike, flight = story.keyframes[-2:]
    expected = {"period": 1, "match_second": arrival, "phase": "flight", "event_type": "shot", "player_id": "kba-11",
                "receiver_id": None, "ball": list(ball), "positions": [list(p) for p in strike.positions]}
    assert flight.to_dict() == expected
    assert _positions(strike.positions)[_keeper(metadata.away)] == SAVE_KEEPER_SPOT


SIMULATED_SAVE_SEED = 194
BALL_ROUNDING_M = 0.05


def test_every_simulated_saved_shot_stops_short_of_its_goal_line_with_the_keeper_on_the_ball() -> None:
    """Seed 194 replays saved shots at both goals; each stops in front of the line and the keeper meets the ball."""
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", SIMULATED_SAVE_SEED))
    sim = result.metadata
    analyzer, tracking = MatchAnalyzer(sim), TrackingModel(sim)
    frames: dict[str, Frame] = {}
    goals_seen: set[bool] = set()
    for index, event in enumerate(result.events):
        analyzer.ingest(event, tracking.previous or None)
        frames[event.event_id] = tracking.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
        if event.event_type is not EventType.SHOT or event.shot_result is not ShotResult.SAVED:
            continue
        assert event.team_id is not None
        story = build_story(result.events[:index + 1], frames, {}, sim, event.period, event.match_second)
        assert story is not None
        flight = story.keyframes[-1]
        attacks_right = sim.side_of(event.team_id) is Side.HOME
        depth = PITCH_LENGTH_M - flight.ball[0] if attacks_right else flight.ball[0]
        goals_seen.add(attacks_right)
        assert SAVE_MIN_DEPTH_M - BALL_ROUNDING_M <= depth <= SAVE_MAX_DEPTH_M + BALL_ROUNDING_M
        keeper = _keeper(sim.team(sim.side_of(event.team_id).opponent))
        assert _positions(flight.positions)[keeper] == flight.ball
    assert goals_seen == {True, False}
