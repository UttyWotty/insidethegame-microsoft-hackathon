"""Tests for the automated highlights reel and its narration.

They check clip selection (goals first, half-time limited to the first half), frame windows around each moment,
narration priority, and the grounded fallback caption. All logic is pure.
"""

from insidegame.agents.recap_context import RecapStage
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.highlights.reel import (
    LEAD_S,
    MAX_CLIPS,
    TAIL_S,
    FrameRecord,
    Narration,
    build_reel,
    clip_frames,
    select_moments,
)
from insidegame.live.highlight_lines import clip_narrations
from insidegame.live.producer import AirStatus, BroadcastRecord


def _moment(mid: str, kind: MomentKind, period: int, second: float, importance: float) -> KeyMoment:
    return KeyMoment(mid, kind, period, second, importance, "home", facts={"player": "Zane Soler"})


def _frame(period: int, second: float) -> FrameRecord:
    return FrameRecord(period, second, "pass", "p1", (50.0, 34.0), [("p1", 50.0, 34.0)])


def test_reels_keep_every_goal_and_the_biggest_moments_in_match_order() -> None:
    moments = [_moment(f"m{i}", MomentKind.MOMENTUM_SWING, 1, 100.0 * i, 0.5 + i / 100) for i in range(10)]
    moments += [_moment("g1", MomentKind.GOAL, 1, 950.0, 0.9), _moment("g2", MomentKind.GOAL, 2, 3000.0, 0.95),
                _moment("low", MomentKind.CHAOS_SPELL, 1, 50.0, 0.1)]
    half = select_moments(moments, RecapStage.HALF_TIME)
    full = select_moments(moments, RecapStage.FULL_TIME)
    assert len(full) == MAX_CLIPS and {"g1", "g2"} <= {m.moment_id for m in full}
    assert all(m.period == 1 for m in half) and "low" not in {m.moment_id for m in full}
    assert [(m.period, m.match_second) for m in full] == sorted((m.period, m.match_second) for m in full)


def test_clips_cut_frames_around_the_moment_in_its_period() -> None:
    moment = _moment("g1", MomentKind.GOAL, 2, 600.0, 0.9)
    frames = [_frame(2, 600.0 - LEAD_S - 1), _frame(2, 595.0), _frame(2, 600.0 + TAIL_S), _frame(1, 600.0)]
    assert [(f.period, f.match_second) for f in clip_frames(frames, moment)] == [(2, 595.0), (2, 604.0)]


def test_narration_prefers_the_viewer_cue_then_the_desk_then_the_facts() -> None:
    record = BroadcastRecord("g1", "10'", "goal", 0.9, {}, "Soler breaks the deadlock!", False, AirStatus.AIRED)
    cues = [{"moment_id": "g1", "commentary": "Soler abre el marcador!", "commentary_language": "es"}]
    assert clip_narrations(cues, {"g1": record})["g1"] == Narration("Soler abre el marcador!", "es")
    assert clip_narrations([], {"g1": record})["g1"].text == "Soler breaks the deadlock!"
    moments = [_moment("g1", MomentKind.GOAL, 1, 600.0, 0.9), _moment("s1", MomentKind.GREAT_SAVE, 1, 900.0, 0.8)]
    reel = build_reel(moments, RecapStage.HALF_TIME, [_frame(1, 598.0), _frame(1, 899.0)],
                      clip_narrations([], {"g1": record}))
    assert [c.narration.text for c in reel] == ["Soler breaks the deadlock!", "16' Great save: Zane Soler."]
    assert reel[0].to_dict()["actor"] == "Zane Soler"
    assert reel[0].to_dict()["intensity"] == "peak" and reel[0].to_dict()["frames"][0]["ball"] == [50.0, 34.0]
