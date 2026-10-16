"""Tests for ShapeTracker and the shape_shift facts on scripted event and position streams (no simulator).

They check when a shift fires (size, sustain, cooldown, possession, period resets, missing positions), that the
window possession and space-control shares match an independent recomputation, and the trigger classification.
They also check that the facts carry exactly the documented keys and that every summary number is a fact.
"""

import statistics

import pytest
from shape_helpers import STEP_S, Stream, event, fixture, positions_for, run_stream, step_line

from insidegame.agents.grounding import collect_evidence_numbers, extract_numbers
from insidegame.analytics import shape_tracker
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import FactValue
from insidegame.analytics.rhythm import RhythmReading, RhythmState
from insidegame.analytics.shape_moments import ShiftTrigger, shape_facts, shift_trigger
from insidegame.analytics.shape_tracker import (
    CONTROL_SAMPLE_S,
    SHAPE_WINDOW_S,
    SHIFT_COOLDOWN_S,
    SHIFT_MIN_M,
    SHIFT_SUSTAIN_S,
    ShapeShift,
    ShapeTracker,
    ShiftDirection,
    WindowSummary,
)
from insidegame.core.geometry import Point
from insidegame.domain.enums import EventType
from insidegame.studio.control import PERCENT, space_control

BEFORE_M = 30.0
DROP_AT_S = 1500.0
END_S = 3500.0
FIRST_FIRE_S = 2110.0
FACT_KEYS = frozenset({
    "team", "opponent", "direction", "line_before_m", "line_after_m", "line_change_m", "block_before", "block_after",
    "length_before_m", "length_after_m", "width_before_m", "width_after_m", "control_before_pct",
    "control_after_pct", "possession_before_pct", "possession_after_pct", "minutes_compared", "score",
    "goal_difference", "trigger", "trigger_minute", "momentum_with", "summary",
})
POSSESSION_CYCLE_S = 70.0
HOME_BALL_S = 20.0
LEVEL = RhythmReading(0.0, 0.0, 0.0, 0.0, 0.0, 0.5, RhythmState.BALANCED)


def _drop(size_m: float, **kwargs: object) -> Stream:
    return run_stream(step_line(BEFORE_M, BEFORE_M - size_m, DROP_AT_S), END_S, **kwargs)  # type: ignore[arg-type]


def test_a_sustained_drop_fires_once_after_the_sustain() -> None:
    stream = _drop(SHIFT_MIN_M + 4.0)
    assert len(stream.shifts) == 1
    shift = stream.shifts[0]
    assert shift.direction is ShiftDirection.DROPPED and shift.team_id == "kba" and shift.opponent_id == "irv"
    assert shift.before.line_height_m == pytest.approx(BEFORE_M) and shift.after.line_height_m == pytest.approx(20.0)
    first_met = DROP_AT_S + SHAPE_WINDOW_S * SHIFT_MIN_M / 10.0
    assert shift.match_second >= first_met + SHIFT_SUSTAIN_S - STEP_S and shift.match_second == FIRST_FIRE_S
    assert shift.line_change_m == pytest.approx(10.0) and shift.window_s == SHAPE_WINDOW_S


def test_a_drop_shorter_than_the_sustain_does_not_fire() -> None:
    stream = _drop(SHIFT_MIN_M + 1.0)
    assert stream.sustained and not stream.shifts


def test_a_drop_smaller_than_the_threshold_does_not_fire() -> None:
    stream = _drop(SHIFT_MIN_M - 1.0)
    assert not stream.sustained and not stream.shifts


def test_in_possession_frames_are_ignored() -> None:
    stream = _drop(SHIFT_MIN_M + 4.0, home_has_ball=lambda second: True)
    assert not stream.shifts
    assert stream.tracker.reading("kba") is None and stream.tracker.reading("irv") is not None


def test_cooldown_suppresses_a_second_shift(monkeypatch: pytest.MonkeyPatch) -> None:
    def line(second: float) -> float:
        return BEFORE_M if second < DROP_AT_S else (20.0 if second < 2150.0 else 32.0)

    cooled = run_stream(line, END_S)
    assert [s.direction for s in cooled.shifts] == [ShiftDirection.DROPPED, ShiftDirection.PUSHED_UP]
    assert cooled.shifts[1].match_second - cooled.shifts[0].match_second >= SHIFT_COOLDOWN_S
    monkeypatch.setattr(shape_tracker, "SHIFT_COOLDOWN_S", 0.0)
    eager = run_stream(line, END_S)
    assert eager.shifts[1].match_second - eager.shifts[0].match_second < SHIFT_COOLDOWN_S


def test_period_start_resets_samples_and_pending_shifts() -> None:
    stream = _drop(SHIFT_MIN_M + 4.0, period_starts=(2000.0,))
    assert stream.sustained and not stream.shifts
    assert stream.tracker.reading("kba") is not None and stream.tracker.timeline()[-1].period == 2
    after_reset = run_stream(step_line(BEFORE_M, 20.0, DROP_AT_S), 2010.0, period_starts=(2000.0,))
    assert after_reset.tracker.reading("kba") is None


def test_no_positions_or_no_events_give_no_shift_and_no_reading() -> None:
    blind = _drop(SHIFT_MIN_M + 4.0, with_positions=False)
    assert not blind.shifts and blind.tracker.reading("kba") is None and not blind.tracker.timeline()
    empty = ShapeTracker(fixture())
    assert empty.reading("kba") is None and empty.reading("irv") is None and empty.timeline() == []


def _expected_possession(stream: Stream, start: float, end: float, include_end: bool) -> float:
    """Independent recomputation: each event's elapsed time belongs to the side that had the ball before it."""
    holder, last, held, total = "irv", 0.0, 0.0, 0.0
    for item in stream.events:
        inside = start <= item.match_second < end or (include_end and item.match_second == end)
        if inside:
            total += item.match_second - last
            held += item.match_second - last if holder == "kba" else 0.0
        last = item.match_second
        if item.event_type in (EventType.KICK_OFF, EventType.POSSESSION_CHANGE):
            holder = str(item.team_id)
    return PERCENT * held / total


def _expected_control(stream: Stream, start: float, end: float, include_end: bool) -> float:
    home_ids = frozenset(p.player_id for p in stream.metadata.home.players)
    seconds = sorted(stream.frames)
    sampled = [s for i, s in enumerate(seconds) if i % int(CONTROL_SAMPLE_S // STEP_S) == 0]
    shares = [space_control([(pid, p.x, p.y) for pid, p in stream.frames[s].items()], home_ids).home_share
              for s in sampled if start <= s < end or (include_end and s == end)]
    return statistics.fmean(shares)


def test_window_possession_and_control_shares_match_a_recomputation() -> None:
    stream = _drop(SHIFT_MIN_M + 4.0, home_has_ball=lambda second: second % POSSESSION_CYCLE_S < HOME_BALL_S)
    shift = stream.shifts[0]
    split, start = shift.match_second - SHAPE_WINDOW_S, shift.match_second - 2 * SHAPE_WINDOW_S
    assert shift.before.possession_pct == pytest.approx(_expected_possession(stream, start, split, False))
    assert shift.after.possession_pct == pytest.approx(_expected_possession(stream, split, shift.match_second, True))
    assert shift.before.control_pct == pytest.approx(_expected_control(stream, start, split, False))
    assert shift.after.control_pct == pytest.approx(_expected_control(stream, split, shift.match_second, True))
    assert shift.after.control_pct < shift.before.control_pct
    assert 0.0 < shift.after.possession_pct < PERCENT  # type: ignore[operator]


def test_goals_set_the_trigger() -> None:
    went_ahead = _drop(SHIFT_MIN_M + 4.0, goals={1400.0: ("kba", 1, 0)})
    shift = went_ahead.shifts[0]
    assert shift.last_goal == ("kba", 1400.0, 1, 0) and (shift.score_home, shift.score_away) == (1, 0)
    assert shift_trigger(shift, went_ahead.metadata) is ShiftTrigger.WENT_AHEAD
    conceded = _drop(SHIFT_MIN_M + 4.0, goals={1400.0: ("irv", 0, 1)})
    assert shift_trigger(conceded.shifts[0], conceded.metadata) is ShiftTrigger.CONCEDED
    too_early = _drop(SHIFT_MIN_M + 4.0, goals={500.0: ("kba", 1, 0)})
    assert too_early.shifts[0].last_goal is None
    assert shift_trigger(too_early.shifts[0], too_early.metadata) is ShiftTrigger.NONE


def _shift(last_goal: tuple[str, float, int, int] | None, score: tuple[int, int],
           control: float | None = 52.0) -> ShapeShift:
    before = WindowSummary(31.12, 50.0, 40.0, control, 65.14, 40)
    after = WindowSummary(20.04, 49.0, 39.5, None if control is None else 46.27, 49.8, 40)
    return ShapeShift("kba", "irv", ShiftDirection.DROPPED, 2, 5280.0, before, after, SHAPE_WINDOW_S,
                      score[0], score[1], last_goal)


@pytest.mark.parametrize(("goal", "score", "trigger"), [
    (("kba", 4620.0, 2, 1), (2, 1), ShiftTrigger.WENT_AHEAD),
    (("kba", 4620.0, 3, 1), (3, 1), ShiftTrigger.EXTENDED_LEAD),
    (("kba", 4620.0, 1, 1), (1, 1), ShiftTrigger.EQUALISED),
    (("kba", 4620.0, 1, 2), (1, 2), ShiftTrigger.PULLED_ONE_BACK),
    (("irv", 4620.0, 1, 1), (1, 1), ShiftTrigger.CONCEDED),
    (None, (0, 0), ShiftTrigger.NONE),
])
def test_facts_carry_exactly_the_documented_keys_and_every_summary_number(
    goal: tuple[str, float, int, int] | None, score: tuple[int, int], trigger: ShiftTrigger,
) -> None:
    metadata = fixture()
    facts = shape_facts(_shift(goal, score), metadata, LEVEL)
    assert set(facts) == FACT_KEYS and facts["trigger"] == trigger.value
    assert all(isinstance(v, (str, int, float, bool)) or v is None for v in facts.values())
    assert isinstance(facts["minutes_compared"], int) and isinstance(facts["goal_difference"], int)
    assert facts["line_before_m"] == 31.1 and facts["line_after_m"] == 20.0 and facts["block_after"] == "low"
    assert facts["score"] == f"{score[0]}-{score[1]}" and facts["momentum_with"] == "neither"
    assert (facts["trigger_minute"] is None) == (trigger is ShiftTrigger.NONE)
    summary = str(facts["summary"])
    assert summary.startswith("After ") != (trigger is ShiftTrigger.NONE)
    _assert_summary_numbers_are_facts(facts, summary)


def _assert_summary_numbers_are_facts(facts: dict[str, FactValue], summary: str) -> None:
    present = collect_evidence_numbers({k: v for k, v in facts.items() if k != "summary"})
    assert all(n in present for n in extract_numbers(summary)), summary


def test_summary_leaves_out_missing_control_and_names_momentum() -> None:
    metadata = fixture()
    surging = RhythmReading(-0.6, 0.0, 0.4, 0.0, 0.0, 0.5, RhythmState.AWAY_PRESSURE)
    facts = shape_facts(_shift(None, (0, 0), control=None), metadata, surging)
    summary = str(facts["summary"])
    assert "share of the pitch" not in summary and "possession went from 65.1% to 49.8%" in summary
    assert facts["control_before_pct"] is None and facts["momentum_with"] == metadata.away.name
    _assert_summary_numbers_are_facts(facts, summary)


def test_an_empty_positions_map_adds_no_sample_and_does_not_crash() -> None:
    metadata = fixture()
    tracker = ShapeTracker(metadata)
    tracker.observe(event(metadata, 0, 0.0, EventType.KICK_OFF, "kba"), None)
    assert tracker.observe(event(metadata, 1, STEP_S, EventType.PASS, "kba"), {}) == ()
    assert tracker.reading("irv") is None and tracker.timeline() == []


@pytest.mark.parametrize(("goal", "expected"), [
    (("kba", 1, 1), ShiftTrigger.EQUALISED), (("kba", 1, 2), ShiftTrigger.PULLED_ONE_BACK),
    (("kba", 3, 1), ShiftTrigger.EXTENDED_LEAD), (("irv", 1, 1), ShiftTrigger.CONCEDED),
])
def test_every_trigger_class_follows_the_score_after_the_goal(goal: tuple[str, int, int],
                                                              expected: ShiftTrigger) -> None:
    window = WindowSummary(BEFORE_M, BEFORE_M, BEFORE_M, None, None, 0)
    scorer, home, away = goal
    shift = ShapeShift("kba", "irv", ShiftDirection.DROPPED, 2, END_S, window, window, SHAPE_WINDOW_S, home, away,
                       (scorer, DROP_AT_S, home, away))
    assert shift_trigger(shift, fixture()) is expected


def test_reading_is_none_for_a_team_that_is_not_in_the_match() -> None:
    stream = _drop(SHIFT_MIN_M + 4.0)
    assert stream.tracker.reading("kba") is not None
    assert stream.tracker.reading("not-a-team") is None


def test_the_analyzer_ingests_an_empty_positions_map_without_crashing() -> None:
    metadata = fixture()
    analyzer = MatchAnalyzer(metadata)
    analyzer.ingest(event(metadata, 0, 0.0, EventType.KICK_OFF, "kba"), None)
    analyzer.ingest(event(metadata, 1, STEP_S, EventType.PASS, "kba"), {})
    assert analyzer.shape.reading("irv") is None and analyzer.shape.timeline() == []


def test_unknown_players_and_non_finite_points_are_left_out_of_space_control() -> None:
    metadata = fixture()
    tracker = ShapeTracker(metadata)
    tracker.observe(event(metadata, 0, 0.0, EventType.KICK_OFF, "kba"), None)
    lost = metadata.home.players[0].player_id
    junk = {"ghost": Point(10.0, 10.0), lost: Point(float("nan"), 5.0)}
    tracker.observe(event(metadata, 1, STEP_S, EventType.PASS, "kba"), junk)
    assert len(tracker.control) == 0
    frame = positions_for(metadata, BEFORE_M)
    tracker.observe(event(metadata, 2, 2 * STEP_S, EventType.PASS, "kba"), frame | junk)
    kept = [(pid, p.x, p.y) for pid, p in frame.items() if pid != lost]
    expected = space_control(kept, tracker.home_ids).home_share
    assert [share for _, share in tracker.control] == [expected]


def test_a_frame_with_only_one_team_samples_that_team_and_gives_it_all_the_space() -> None:
    metadata = fixture()
    tracker = ShapeTracker(metadata)
    tracker.observe(event(metadata, 0, 0.0, EventType.KICK_OFF, "irv"), None)
    home_ids = {p.player_id for p in metadata.home.players}
    home_only = {pid: p for pid, p in positions_for(metadata, BEFORE_M).items() if pid in home_ids}
    assert tracker.observe(event(metadata, 1, STEP_S, EventType.PASS, "irv"), home_only) == ()
    assert [share for _, share in tracker.control] == [100.0]
    assert [m.line_height_m for _, m in tracker.samples["kba"]] == [pytest.approx(BEFORE_M)]
    assert len(tracker.samples["irv"]) == 0
