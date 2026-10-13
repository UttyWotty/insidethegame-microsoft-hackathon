"""Tests for deterministic play-by-play commentary.

They check that commentary starts at kick-off, is paced, names real players, marks period changes, and lifts
its intensity for close calls and goals.
Inputs come from a full simulated match.
"""

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.commentary.play_by_play import (
    FILLER_GAP_FACTOR,
    MAX_MATCH_GAP_S,
    MIN_GAP_S,
    MIN_MATCH_GAP_S,
    RECENT_LINES,
    PlayByPlay,
    line_gap_for_speed,
)
from insidegame.domain.enums import Intensity
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

FIRST_MINUTES = 3
MIN_LINES_PER_MATCH = 60


def _lines() -> list:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    analyzer, pbp = MatchAnalyzer(result.metadata), PlayByPlay(result.metadata)
    return [line for event in result.events if (line := pbp.observe(analyzer.ingest(event)))]


def test_commentary_starts_at_kick_off_and_continues_through_the_match() -> None:
    lines = _lines()
    assert lines[0].text.startswith("Kick-off at") and lines[0].minute == "1'"
    assert sum(1 for line in lines if line.period == 1 and line.match_second < FIRST_MINUTES * 60) >= 2
    assert len(lines) >= MIN_LINES_PER_MATCH


def test_paced_lines_respect_the_minimum_gap() -> None:
    paced = [line for line in _lines() if line.kind == "play"]
    gaps = [b.match_second - a.match_second for a, b in zip(paced, paced[1:], strict=False) if a.period == b.period]
    assert min(gaps) >= MIN_GAP_S


def test_period_changes_are_called() -> None:
    texts = [line.text for line in _lines()]
    assert any(t.startswith("Half-time:") for t in texts) and any(t.startswith("Full-time:") for t in texts)
    assert any("second half" in t for t in texts)


def test_every_goal_gets_a_peak_line_with_the_new_score() -> None:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    analyzer, pbp = MatchAnalyzer(result.metadata), PlayByPlay(result.metadata)
    lines = [line for event in result.events if (line := pbp.observe(analyzer.ingest(event)))]
    goals = [line for line in lines if line.kind == "goal"]
    assert len(goals) == result.home_goals + result.away_goals
    assert all(line.intensity is Intensity.PEAK and "!" in line.text for line in goals)
    assert f"{result.home_goals}-{result.away_goals}" in goals[-1].text
    assert all(line.to_dict()["intensity"] == "peak" for line in goals)


def test_close_calls_are_raised_and_ordinary_play_stays_normal() -> None:
    lines = _lines()
    close_calls = [line for line in lines if line.kind == "close_call"]
    assert close_calls and all(line.intensity is Intensity.RAISED for line in close_calls)
    assert all(line.intensity is Intensity.NORMAL for line in lines if line.kind == "play")


def test_lines_do_not_repeat_soon_or_stack_the_same_kind_of_action() -> None:
    texts = [line.text for line in _lines() if line.kind == "play"]
    for i, text in enumerate(texts):
        assert text not in texts[max(0, i - RECENT_LINES):i]
    assert all(a != b for a, b in zip(texts, texts[1:]))


def test_line_gap_keeps_a_steady_viewing_rhythm_across_replay_speeds() -> None:
    assert line_gap_for_speed(10.0) == MIN_GAP_S
    assert line_gap_for_speed(1.0) == MIN_MATCH_GAP_S
    assert line_gap_for_speed(600.0) == MAX_MATCH_GAP_S
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))

    def count(gap: float) -> int:
        analyzer, pbp = MatchAnalyzer(result.metadata), PlayByPlay(result.metadata, min_gap_s=gap)
        return sum(1 for event in result.events if pbp.observe(analyzer.ingest(event)))

    assert count(line_gap_for_speed(1.0)) > count(line_gap_for_speed(10.0)) > count(line_gap_for_speed(60.0))


def test_real_time_viewing_sets_the_scene_in_the_first_lull_and_avoids_long_silences() -> None:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    analyzer, pbp = MatchAnalyzer(result.metadata), PlayByPlay(result.metadata, min_gap_s=line_gap_for_speed(1.0))
    lines = [line for event in result.events if (line := pbp.observe(analyzer.ingest(event)))]
    intro = [line for line in lines if line.kind == "intro"]
    assert len(intro) == 1 and lines[0].kind == "kick_off" and "press high" in intro[0].text
    before = lines[lines.index(intro[0]) - 1]
    assert intro[0].match_second - before.match_second >= FILLER_GAP_FACTOR * line_gap_for_speed(1.0)
    assert intro[0].match_second < 60
    first_half = [line.match_second for line in lines if line.period == 1]
    gaps = sorted(b - a for a, b in zip(first_half, first_half[1:]))
    assert gaps[len(gaps) // 2] <= 30
