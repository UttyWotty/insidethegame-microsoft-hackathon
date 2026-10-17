"""Tests for the non-shot reel sequence: which actions a window keeps, their keyframes, and the final arrival.

Events, tracking frames, and moments are built by hand in the style of the reel-story tests, so every keyframe's
ball, time, and aligned player can be checked exactly, including an away action mirrored into the home frame.
They also pin the arrival clamps, the shot and empty-window cases, the shared build-up keyframe, and the imports.
"""

import ast
from pathlib import Path

import pytest

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights import reel_sequence
from insidegame.highlights.reel_sequence import (
    ARRIVAL_MAX_S,
    ARRIVAL_MIN_S,
    arrival_keyframe,
    arrival_player,
    arrival_second,
    clip_sequence,
    window_actions,
)
from insidegame.highlights.reel_story import StorySource
from insidegame.highlights.replay_story import ReplayPhase, action_keyframe, build_story
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import Frame

HOME, AWAY = "kba", "irv"
POSSESSION = 5
MOMENT_AT = 95.0
LEAD_S = 5.0
TAIL_S = 4.0
LATE_AT = 100.0
SHOT_AT = 100.5
SWING_AT = 300.0
NO_FRAME_ID = "nf"
FORBIDDEN_LAYERS = ("simulation", "live", "api", "agents", "orchestration", "datasets")


@pytest.fixture(scope="module")
def metadata() -> MatchMetadata:
    return build_fixture("kestrel_bay", "ironvale", 1)


def _event(eid: str, second: float, kind: EventType, team: str, player: str, start: tuple[float, float] | None,
           end: tuple[float, float] | None = None, receiver: str | None = None,
           outcome: Outcome | None = Outcome.SUCCESS, period: int = 1, **detail: object) -> MatchEvent:
    return MatchEvent(eid, "m", 0, period, second, kind, team, player, POSSESSION,
                      Point(*start) if start else None, 0, 0, end=Point(*end) if end else None, outcome=outcome,
                      receiver_id=receiver, **detail)  # type: ignore[arg-type]


def _events() -> list[MatchEvent]:
    """A home pass and carry, a failed home pass won by the away side, an away carry and pass, then a shot.

    Around them sit events a window must drop: one second either side of the window, a pressure, an action with
    no stored frame, and an action in the other period.
    """
    return [
        _event("early", 89.0, EventType.PASS, HOME, "kba-02", (10.0, 30.0), (20.0, 30.0), "kba-04"),
        _event("a1", 91.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (40.0, 30.0), "kba-08"),
        _event("pr", 92.0, EventType.PRESSURE, AWAY, "irv-08", (60.0, 38.0)),
        _event("a2", 93.0, EventType.CARRY, HOME, "kba-08", (40.0, 30.0), (50.0, 34.0)),
        _event(NO_FRAME_ID, 94.0, EventType.CARRY, HOME, "kba-08", (50.0, 34.0), (50.0, 34.0)),
        _event("p2", 95.0, EventType.PASS, HOME, "kba-04", (50.0, 34.0), (60.0, 30.0), "kba-08", period=2),
        _event("a3", MOMENT_AT, EventType.PASS, HOME, "kba-08", (50.0, 34.0), (70.0, 20.0), "kba-11",
               outcome=Outcome.FAILURE),
        _event("a4", 97.0, EventType.CARRY, AWAY, "irv-05", (35.0, 48.0), (45.0, 40.0)),
        _event("late", LATE_AT, EventType.PASS, AWAY, "irv-05", (45.0, 40.0), (60.0, 40.0), "irv-09"),
        _event("sh", SHOT_AT, EventType.SHOT, AWAY, "irv-09", (90.0, 30.0), (105.0, 33.0), outcome=None,
               shot_result=ShotResult.SAVED, ball_speed_kmh=80.0),
    ]


def _frame(metadata: MatchMetadata) -> Frame:
    """All 22 players in two rows, away from every ball spot used here."""
    rows = [(p.player_id, 5.0, 2.0 + 3.0 * i) for i, p in enumerate(metadata.home.players)]
    return rows + [(p.player_id, 100.0, 2.0 + 3.0 * i) for i, p in enumerate(metadata.away.players)]


def _source(metadata: MatchMetadata, events: list[MatchEvent] | None = None) -> StorySource:
    played = events if events is not None else _events()
    return StorySource(played, {e.event_id: _frame(metadata) for e in played if e.event_id != NO_FRAME_ID}, {},
                       metadata)


def _moment(kind: MomentKind, second: float, event_ids: tuple[str, ...]) -> KeyMoment:
    return KeyMoment("m1", kind, 1, second, 0.9, HOME, event_ids=event_ids, facts={"player": "Zane Soler"})


def _position(frame: Frame, player_id: str) -> tuple[float, float]:
    return next((x, y) for pid, x, y in frame if pid == player_id)


def test_window_actions_keep_only_framed_passes_and_carries_in_the_window(metadata: MatchMetadata) -> None:
    source = _source(metadata)
    kept = window_actions(source.events, source.frames, 1, MOMENT_AT - LEAD_S, MOMENT_AT + TAIL_S)
    assert [source.events[i].event_id for i in kept] == ["a1", "a2", "a3", "a4"]


def test_window_actions_drop_actions_missing_a_start_end_or_team(metadata: MatchMetadata) -> None:
    events = [_event("ns", 92.0, EventType.PASS, HOME, "kba-04", None, (40.0, 30.0)),
              _event("ne", 93.0, EventType.CARRY, HOME, "kba-04", (40.0, 30.0)),
              MatchEvent("nt", "m", 0, 1, 94.0, EventType.PASS, None, "kba-04", POSSESSION, Point(1.0, 1.0), 0, 0,
                         end=Point(2.0, 2.0))]
    frames = {e.event_id: _frame(metadata) for e in events}
    assert window_actions(events, frames, 1, 90.0, 99.0) == []


def test_clip_sequence_has_one_build_up_keyframe_per_action_then_the_arrival(metadata: MatchMetadata) -> None:
    keyframes = clip_sequence(_moment(MomentKind.THREAT_CREATED, MOMENT_AT, ("a3",)), _source(metadata),
                              LEAD_S, TAIL_S)
    assert keyframes is not None
    assert [k.phase for k in keyframes] == [ReplayPhase.BUILD_UP] * 5
    assert [k.match_second for k in keyframes] == [91.0, 93.0, MOMENT_AT, 97.0, LATE_AT]
    assert [k.ball for k in keyframes[:3]] == [(20.0, 30.0), (40.0, 30.0), (50.0, 34.0)]
    assert [k.player_id for k in keyframes[:4]] == ["kba-04", "kba-08", "kba-08", "irv-05"]
    for k in keyframes[:4]:
        assert k.player_id is not None and _position(k.positions, k.player_id) == k.ball


def test_an_away_action_is_mirrored_into_the_home_frame(metadata: MatchMetadata) -> None:
    keyframes = clip_sequence(_moment(MomentKind.THREAT_CREATED, MOMENT_AT, ("a3",)), _source(metadata),
                              LEAD_S, TAIL_S)
    assert keyframes is not None
    away = keyframes[3]
    start = mirror(Point(35.0, 48.0))
    assert away.ball == (start.x, start.y) == (70.0, 20.0)


def test_the_arrival_lands_on_the_last_actions_end_with_the_carrier(metadata: MatchMetadata) -> None:
    keyframes = clip_sequence(_moment(MomentKind.MOMENTUM_SWING, MOMENT_AT, ()), _source(metadata), LEAD_S, TAIL_S)
    assert keyframes is not None
    arrival = keyframes[-1]
    end = mirror(Point(45.0, 40.0))
    assert arrival.ball == (end.x, end.y)
    assert arrival.match_second == LATE_AT and arrival.event_type == "carry"
    assert arrival.player_id == "irv-05" and arrival.receiver_id is None
    assert _position(arrival.positions, "irv-05") == arrival.ball


def test_a_pass_arrival_goes_to_the_receiver_and_a_failed_pass_aligns_no_one(metadata: MatchMetadata) -> None:
    frame = _frame(metadata)
    done = _event("ok", 10.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (40.0, 35.0), "kba-08")
    landed = arrival_keyframe(done, frame, 12.0, metadata)
    assert landed.player_id == "kba-08" and _position(landed.positions, "kba-08") == (40.0, 35.0)
    lost = _event("ko", 10.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (40.0, 35.0), "kba-08",
                  outcome=Outcome.FAILURE)
    loose = arrival_keyframe(lost, frame, 12.0, metadata)
    assert loose.player_id is None and loose.ball == (40.0, 35.0) and loose.positions == frame


@pytest.mark.parametrize("kind, outcome, receiver, expected", [
    (EventType.PASS, Outcome.SUCCESS, "kba-08", "kba-08"),
    (EventType.PASS, Outcome.FAILURE, "kba-08", None),
    (EventType.PASS, None, "kba-08", None),
    (EventType.CARRY, Outcome.SUCCESS, None, "kba-04"),
    (EventType.CARRY, Outcome.FAILURE, None, "kba-04"),
    (EventType.SHOT, None, None, None),
])
def test_the_arrival_player_is_the_completed_receiver_or_the_carrier(kind: EventType, outcome: Outcome | None,
                                                                    receiver: str | None,
                                                                    expected: str | None) -> None:
    action = _event("x", 10.0, kind, HOME, "kba-04", (20.0, 30.0), (40.0, 35.0), receiver, outcome=outcome)
    assert arrival_player(action) == expected


@pytest.mark.parametrize("gap, expected", [(8.0, ARRIVAL_MAX_S), (0.1, ARRIVAL_MIN_S), (2.5, 2.5)])
def test_the_arrival_gap_is_clamped(gap: float, expected: float) -> None:
    events = [_event("a", 10.0, EventType.PASS, HOME, "kba-04", (20.0, 30.0), (40.0, 30.0), "kba-08"),
              _event("same", 10.0, EventType.PRESSURE, AWAY, "irv-08", (30.0, 30.0)),
              _event("other", 10.0 + gap / 2, EventType.PRESSURE, AWAY, "irv-08", (30.0, 30.0), period=2),
              _event("next", 10.0 + gap, EventType.PASS, HOME, "kba-08", (40.0, 30.0), (50.0, 30.0), "kba-04")]
    assert arrival_second(events, 0) == pytest.approx(10.0 + expected)


def test_the_arrival_gap_is_the_maximum_when_no_later_event_exists() -> None:
    events = [_event("a", 10.0, EventType.CARRY, HOME, "kba-04", (20.0, 30.0), (40.0, 30.0))]
    assert arrival_second(events, 0) == 10.0 + ARRIVAL_MAX_S


@pytest.mark.parametrize("kind", [MomentKind.GOAL, MomentKind.GREAT_SAVE, MomentKind.BIG_CHANCE_MISSED])
def test_shot_moments_get_no_sequence(metadata: MatchMetadata, kind: MomentKind) -> None:
    assert clip_sequence(_moment(kind, SHOT_AT, ("sh",)), _source(metadata), LEAD_S, TAIL_S) is None


def test_an_empty_window_gets_no_sequence(metadata: MatchMetadata) -> None:
    assert clip_sequence(_moment(MomentKind.MOMENTUM_SWING, SWING_AT, ()), _source(metadata), LEAD_S, TAIL_S) is None


def test_action_keyframe_matches_the_replay_story_build_up(metadata: MatchMetadata) -> None:
    events = [_event("c1", 94.0, EventType.CARRY, HOME, "kba-08", (78.0, 32.0), (88.0, 36.0)),
              _event("p1", 97.5, EventType.PASS, HOME, "kba-08", (88.0, 36.0), (95.0, 30.0), "kba-11"),
              _event("s", 99.0, EventType.SHOT, HOME, "kba-11", (95.0, 30.0), (105.0, 33.0), outcome=None,
                     shot_result=ShotResult.GOAL, ball_speed_kmh=72.0)]
    frames = {e.event_id: _frame(metadata) for e in events}
    story = build_story(events, frames, {}, metadata, 1, 99.0)
    assert story is not None
    build_up = [k for k in story.keyframes if k.phase is ReplayPhase.BUILD_UP]
    assert build_up == [action_keyframe(e, frames[e.event_id], HOME, metadata) for e in events[:2]]


def test_reel_sequence_imports_no_higher_layer() -> None:
    tree = ast.parse(Path(reel_sequence.__file__).read_text(encoding="utf-8"))
    modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.split(".")[:2] in (["insidegame", layer] for layer in FORBIDDEN_LAYERS)]


def test_a_failed_pass_to_an_intended_receiver_aligns_no_one(metadata: MatchMetadata) -> None:
    """The simulator keeps receiver_id (the intended teammate) on failed passes; the interceptor wins the ball."""
    frame = _frame(metadata)
    lost = _event("kr", 10.0, EventType.PASS, HOME, "kba-02", (49.5, 36.8), (76.3, 25.7), "kba-11",
                  outcome=Outcome.FAILURE)
    loose = arrival_keyframe(lost, frame, 13.0, metadata)
    assert loose.ball == (76.3, 25.7)
    assert loose.player_id is None and loose.positions == frame
