"""Tests for the reel's shot stories: which moments map to a shot, and how build_reel plays story and frame clips.

Events, tracking frames, and moments are built by hand in the style of the instant-replay tests, so every mapping
and every clip's keyframes can be checked exactly against build_story.
They also pin the narration and order invariance of the reel and the module's import boundary.
"""

import ast
from pathlib import Path

import pytest

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.analytics.recap_basis import RecapStage
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.highlights import reel_story
from insidegame.highlights.reel import LEAD_S, TAIL_S, ClipPlayback, FrameRecord, build_reel, clip_frames
from insidegame.highlights.reel_sequence import clip_sequence
from insidegame.highlights.reel_story import StorySource, clip_story, moment_shot
from insidegame.highlights.replay_story import ReplayPhase, build_story
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import Frame

HOME = "kba"
POSSESSION = 5
SHOT_AT = 99.0
PASS_AT = 60.0
SWING_AT = 300.0
SHOT_SPEED_KMH = 72.0
FORBIDDEN_LAYERS = ("simulation", "live", "api", "agents", "orchestration", "datasets")


@pytest.fixture(scope="module")
def metadata() -> MatchMetadata:
    return build_fixture("kestrel_bay", "ironvale", 1)


def _event(eid: str, second: float, kind: EventType, player: str, start: tuple[float, float],
           end: tuple[float, float] | None = None, receiver: str | None = None,
           outcome: Outcome | None = Outcome.SUCCESS, **detail: object) -> MatchEvent:
    return MatchEvent(eid, "m", 0, 1, second, kind, HOME, player, POSSESSION, Point(*start), 0, 0,
                      end=Point(*end) if end else None, outcome=outcome, receiver_id=receiver,
                      **detail)  # type: ignore[arg-type]


def _events() -> list[MatchEvent]:
    """A long pass, then a two-action build-up into a goal whose GOAL event shares the shot's second."""
    return [
        _event("lp", PASS_AT, EventType.PASS, "kba-04", (20.0, 30.0), (60.0, 30.0), "kba-08", length_m=40.0),
        _event("c1", 94.0, EventType.CARRY, "kba-08", (78.0, 32.0), (88.0, 36.0)),
        _event("p1", 97.5, EventType.PASS, "kba-08", (88.0, 36.0), (95.0, 30.0), "kba-11", length_m=9.2),
        _event("s", SHOT_AT, EventType.SHOT, "kba-11", (95.0, 30.0), (105.0, 33.0), outcome=None,
               shot_result=ShotResult.GOAL, ball_speed_kmh=SHOT_SPEED_KMH),
        _event("g", SHOT_AT, EventType.GOAL, "kba-11", (95.0, 30.0), outcome=None),
    ]


def _frame(metadata: MatchMetadata) -> Frame:
    """All 22 players in two rows."""
    rows = [(p.player_id, 20.0, 5.0 + 3.0 * i) for i, p in enumerate(metadata.home.players)]
    return rows + [(p.player_id, 30.0, 5.0 + 3.0 * i) for i, p in enumerate(metadata.away.players)]


def _source(metadata: MatchMetadata, events: list[MatchEvent] | None = None) -> StorySource:
    played = events if events is not None else _events()
    return StorySource(played, {e.event_id: _frame(metadata) for e in played}, {}, metadata)


def _moment(mid: str, kind: MomentKind, second: float, event_ids: tuple[str, ...], importance: float = 0.9) -> KeyMoment:
    return KeyMoment(mid, kind, 1, second, importance, HOME, event_ids=event_ids, facts={"player": "Zane Soler"})


def _record(second: float) -> FrameRecord:
    return FrameRecord(1, second, "pass", "kba-04", (50.0, 34.0), [("kba-04", 50.0, 34.0)])


@pytest.mark.parametrize("kind, ids", [(MomentKind.GOAL, ("s", "g")), (MomentKind.GREAT_SAVE, ("s",)),
                                       (MomentKind.BIG_CHANCE_MISSED, ("s",)), (MomentKind.SPEED_THRESHOLD, ("s",))])
def test_shot_moments_map_to_their_shot(kind: MomentKind, ids: tuple[str, ...]) -> None:
    shot = moment_shot(_moment("m", kind, SHOT_AT, ids), _events())
    assert shot is not None and shot.event_id == "s"


def test_a_goal_only_milestone_maps_to_the_same_second_shot() -> None:
    shot = moment_shot(_moment("hat", MomentKind.MILESTONE, SHOT_AT, ("g",)), _events())
    assert shot is not None and shot.event_id == "s"


@pytest.mark.parametrize("kind, ids", [(MomentKind.DISTANCE_THRESHOLD, ("lp",)), (MomentKind.DISTANCE_THRESHOLD, ("c1",)),
                                       (MomentKind.MOMENTUM_SWING, ()), (MomentKind.GOAL, ("missing", "unknown"))])
def test_pass_carry_empty_and_unknown_moments_have_no_shot(kind: MomentKind, ids: tuple[str, ...]) -> None:
    assert moment_shot(_moment("m", kind, SHOT_AT, ids), _events()) is None


def test_clip_story_is_exactly_the_shots_replay_keyframes(metadata: MatchMetadata) -> None:
    source = _source(metadata)
    story = build_story(source.events, source.frames, source.threats, metadata, 1, SHOT_AT)
    assert story is not None
    assert clip_story(_moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g")), source) == story.keyframes
    assert clip_story(_moment("lp", MomentKind.DISTANCE_THRESHOLD, PASS_AT, ("lp",)), source) is None


def test_clip_story_is_none_when_the_shot_frame_is_missing(metadata: MatchMetadata) -> None:
    source = _source(metadata)
    frames = {eid: f for eid, f in source.frames.items() if eid != "s"}
    gappy = StorySource(source.events, frames, {}, metadata)
    assert clip_story(_moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g")), gappy) is None


def test_shot_clips_play_the_story_keyframes_ending_in_shot_then_flight(metadata: MatchMetadata) -> None:
    source = _source(metadata)
    story = build_story(source.events, source.frames, source.threats, metadata, 1, SHOT_AT)
    assert story is not None
    moments = [_moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g")), _moment("hat", MomentKind.MILESTONE, SHOT_AT, ("g",))]
    reel = build_reel(moments, RecapStage.FULL_TIME, [_record(SHOT_AT - 1.0)], {}, source)
    assert [c.playback for c in reel] == [ClipPlayback.STORY, ClipPlayback.STORY]
    for clip in reel:
        payload = clip.to_dict()
        assert payload["playback"] == "story"
        assert payload["frames"] == [k.to_dict() for k in story.keyframes]
        assert [k["phase"] for k in payload["frames"]][-2:] == [ReplayPhase.SHOT.value, ReplayPhase.FLIGHT.value]


def test_non_shot_clips_play_their_window_sequence_or_keep_the_stored_frames(metadata: MatchMetadata) -> None:
    moments = [_moment("lp", MomentKind.DISTANCE_THRESHOLD, PASS_AT, ("lp",)),
               _moment("sw", MomentKind.MOMENTUM_SWING, SWING_AT, ())]
    records = [_record(PASS_AT - 2.0), _record(PASS_AT + 1.0), _record(SWING_AT - 3.0), _record(SHOT_AT)]
    source = _source(metadata)
    reel = build_reel(moments, RecapStage.FULL_TIME, records, {}, source)
    assert [c.to_dict()["playback"] for c in reel] == ["story", "frames"]
    assert list(reel[0].frames) == clip_sequence(moments[0], source, LEAD_S, TAIL_S)
    assert list(reel[1].frames) == clip_frames(records, moments[1])


def test_a_shot_clip_is_kept_even_without_stored_frames(metadata: MatchMetadata) -> None:
    goal = _moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g"))
    assert build_reel([goal], RecapStage.FULL_TIME, [], {}) == []
    reel = build_reel([goal], RecapStage.FULL_TIME, [], {}, _source(metadata))
    assert len(reel) == 1 and reel[0].playback is ClipPlayback.STORY


def test_stories_never_change_titles_narrations_or_order(metadata: MatchMetadata) -> None:
    moments = [_moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g")),
               _moment("lp", MomentKind.DISTANCE_THRESHOLD, PASS_AT, ("lp",)),
               _moment("sw", MomentKind.MOMENTUM_SWING, SWING_AT, ())]
    records = [_record(PASS_AT), _record(SHOT_AT), _record(SWING_AT)]
    plain = build_reel(moments, RecapStage.FULL_TIME, records, {}, None)
    storied = build_reel(moments, RecapStage.FULL_TIME, records, {}, _source(metadata))
    strip = ("frames", "playback")
    assert [{k: v for k, v in c.to_dict().items() if k not in strip} for c in storied] == \
        [{k: v for k, v in c.to_dict().items() if k not in strip} for c in plain]
    assert [c.playback for c in plain] == [ClipPlayback.FRAMES] * 3


def test_reel_story_imports_no_higher_layer() -> None:
    tree = ast.parse(Path(reel_story.__file__).read_text(encoding="utf-8"))
    modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in modules if m.split(".")[:2] in (["insidegame", layer] for layer in FORBIDDEN_LAYERS)]


def test_a_shot_clip_without_a_story_falls_back_to_stored_frames_or_is_skipped(metadata: MatchMetadata) -> None:
    source = _source(metadata)
    gappy = StorySource(source.events, {eid: f for eid, f in source.frames.items() if eid != "s"}, {}, metadata)
    goal = _moment("g1", MomentKind.GOAL, SHOT_AT, ("s", "g"))
    records = [_record(SHOT_AT - 2.0), _record(SHOT_AT)]
    reel = build_reel([goal], RecapStage.FULL_TIME, records, {}, gappy)
    assert len(reel) == 1 and reel[0].playback is ClipPlayback.FRAMES
    assert list(reel[0].frames) == clip_frames(records, goal)
    assert build_reel([goal], RecapStage.FULL_TIME, [], {}, gappy) == []


def test_a_goal_only_milestone_without_a_same_second_shot_has_no_shot() -> None:
    events = [e for e in _events() if e.event_id != "s"]
    assert moment_shot(_moment("hat", MomentKind.MILESTONE, SHOT_AT, ("g",)), events) is None
