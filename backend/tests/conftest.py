"""Shared pytest fixtures: a fully analysed simulated match and contexts for its key moments.

Fixtures are module-agnostic and session-scoped because simulation is deterministic.
They give agent tests realistic, grounded inputs without any model server.
"""

import pytest

from insidegame.agents.context import MomentContext, build_moment_context
from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import MomentKind
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

FIXTURE_HOME: str = "kestrel_bay"
FIXTURE_AWAY: str = "ironvale"
FIXTURE_SEED: int = 7


@pytest.fixture(scope="session")
def analysed_match() -> tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]:
    """Analyse a full match and capture the first context of every moment kind as it happened."""
    result = simulate_match(build_fixture(FIXTURE_HOME, FIXTURE_AWAY, FIXTURE_SEED))
    analyzer = MatchAnalyzer(result.metadata)
    contexts: dict[MomentKind, MomentContext] = {}
    for event in result.events:
        update = analyzer.ingest(event)
        for moment in update.moments:
            contexts.setdefault(moment.kind, build_moment_context(moment, analyzer))
    return analyzer, contexts


@pytest.fixture(scope="session")
def goal_context(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> MomentContext:
    """Context for the first goal of the fixture match."""
    return analysed_match[1][MomentKind.GOAL]


@pytest.fixture(scope="session")
def tactical_context(analysed_match: tuple[MatchAnalyzer, dict[MomentKind, MomentContext]]) -> MomentContext:
    """Context for the first Tactical Scout flag of the fixture match."""
    return analysed_match[1][MomentKind.TACTICAL_PATTERN]
