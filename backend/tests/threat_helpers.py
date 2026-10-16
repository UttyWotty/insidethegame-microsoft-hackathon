"""Shared helper for expected threat (xT) tests: analyse a simulated match with live tracking positions.

It feeds MatchAnalyzer the tracked positions from before each event, exactly as MatchIntelligenceService.interpret does.
The helper returns every AnalysisUpdate so tests can reconcile per-event threat with running statistics.
"""

from dataclasses import dataclass

from insidegame.analytics.analyzer import AnalysisUpdate, MatchAnalyzer
from insidegame.domain.match import MatchResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture
from insidegame.tracking.model import LOOKAHEAD_EVENTS, TrackingModel


@dataclass(frozen=True)
class TrackedMatch:
    """A simulated match analysed with tracking positions."""

    result: MatchResult
    analyzer: MatchAnalyzer
    updates: list[AnalysisUpdate]


def analyse_with_tracking(home: str, away: str, seed: int) -> TrackedMatch:
    """Simulate a fixture and analyse it with the positions tracked before every event."""
    result = simulate_match(build_fixture(home, away, seed))
    analyzer, tracking = MatchAnalyzer(result.metadata), TrackingModel(result.metadata)
    updates = []
    for index, event in enumerate(result.events):
        updates.append(analyzer.ingest(event, tracking.previous or None))
        tracking.frame(event, result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS])
    return TrackedMatch(result, analyzer, updates)
