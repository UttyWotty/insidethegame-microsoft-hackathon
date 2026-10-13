"""Tests for deterministic play-by-play commentary.

They check that commentary starts at kick-off, is paced, names real players, marks period changes, and lifts
its intensity for close calls and goals.
Inputs come from a full simulated match.
"""

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.commentary.play_by_play import MIN_GAP_S, PlayByPlay
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
