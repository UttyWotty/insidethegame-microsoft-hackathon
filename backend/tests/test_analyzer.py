"""Integration tests running full simulated matches through the stage-two analyzer.

They check that statistics reconcile with raw events and that key moments are consistent.
The pipeline is pure and deterministic, so no mocks are required.
"""

import json

import pytest

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.match import MatchResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

FULL_POSSESSION = 100.0
POSSESSION_TOLERANCE = 0.2


@pytest.fixture(scope="module")
def analysed() -> tuple[MatchResult, MatchAnalyzer]:
    result = simulate_match(build_fixture("kestrel_bay", "ironvale", 7))
    analyzer = MatchAnalyzer(result.metadata)
    for event in result.events:
        analyzer.ingest(event)
    return result, analyzer


def test_team_stats_reconcile_with_events(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    home_id = result.metadata.home.team_id
    home_passes = [e for e in result.events if e.event_type is EventType.PASS and e.team_id == home_id]
    stats = analyzer.stats.teams[home_id]
    assert stats.passes_attempted == len(home_passes)
    assert stats.passes_completed == sum(e.outcome is Outcome.SUCCESS for e in home_passes)
    assert stats.goals == result.home_goals


def test_player_stats_sum_to_team_stats(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    away_id = result.metadata.away.team_id
    players = [p for p in analyzer.stats.players.values() if p.team_id == away_id]
    assert sum(p.shots for p in players) == analyzer.stats.teams[away_id].shots


def test_possession_shares_sum_to_hundred(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    total = sum(analyzer.stats.possession_share(t.team_id) for t in (result.metadata.home, result.metadata.away))
    assert abs(total - FULL_POSSESSION) < POSSESSION_TOLERANCE


def test_one_goal_moment_per_goal(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    goals = [m for m in analyzer.moments if m.kind is MomentKind.GOAL]
    assert len(goals) == result.home_goals + result.away_goals
    assert all(0.0 < m.importance <= 1.0 for m in analyzer.moments)


def test_goal_moments_reference_existing_events(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    event_ids = {e.event_id for e in result.events}
    for moment in analyzer.moments:
        assert set(moment.event_ids) <= event_ids


def test_snapshot_is_json_serialisable(analysed: tuple[MatchResult, MatchAnalyzer]) -> None:
    result, analyzer = analysed
    snapshot = json.loads(json.dumps(analyzer.snapshot()))
    assert snapshot["score"] == {"home": result.home_goals, "away": result.away_goals}
    assert snapshot["rhythm"]["state"]


def test_distance_indicators_fire_at_their_thresholds() -> None:
    from insidegame.analytics.detectors import CARRY_MILESTONES_M, LONG_PASS_THRESHOLD_M
    counts = []
    for seed in range(6):
        result = simulate_match(build_fixture("kestrel_bay", "ironvale", seed))
        analyzer = MatchAnalyzer(result.metadata)
        for event in result.events:
            analyzer.ingest(event)
        tags = [m for m in analyzer.moments if m.kind is MomentKind.DISTANCE_THRESHOLD]
        for tag in tags:
            if tag.facts["indicator"] == "long_pass":
                assert float(tag.facts["length_m"]) >= LONG_PASS_THRESHOLD_M  # type: ignore[arg-type]
            else:
                assert tag.facts["threshold_m"] in CARRY_MILESTONES_M
                assert float(tag.facts["carry_distance_m"]) >= float(tag.facts["threshold_m"])  # type: ignore[arg-type]
        counts.append(len(tags))
    assert 0 < sum(counts) / len(counts) <= 12
