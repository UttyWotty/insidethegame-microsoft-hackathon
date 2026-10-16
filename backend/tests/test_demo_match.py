"""Tests that the documented demo match tells the Tactical Scout story the demo video relies on.

They simulate the demo fixture and compare its scoreline and goal minutes with docs/DEMO_SCRIPT.md.
They also check the flag count, a goal linked to an earlier flag, and that the landing button uses the same seed.
"""

import re
from pathlib import Path

import pytest

from insidegame.analytics.analyzer import MatchAnalyzer
from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED, build_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SCRIPT = REPO_ROOT / "docs" / "DEMO_SCRIPT.md"
LANDING = REPO_ROOT / "frontend" / "src" / "components" / "Landing.tsx"
SETUP_LINE = re.compile(r"seed (\d+), Kestrel Bay vs Ironvale \((\d+)-(\d+), goals at ([^)]+)\)")
MINUTE = re.compile(r"\d+(?:\+\d+)?'")
MAX_FLAGS = 9
MIN_LEAD_MINUTES = 3


@pytest.fixture(scope="module")
def demo_moments() -> tuple[int, int, list[KeyMoment]]:
    result = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, DEMO_SEED))
    analyzer = MatchAnalyzer(result.metadata)
    for event in result.events:
        analyzer.ingest(event)
    return result.home_goals, result.away_goals, analyzer.moments


def test_demo_script_matches_the_simulated_demo_match(demo_moments: tuple[int, int, list[KeyMoment]]) -> None:
    found = SETUP_LINE.search(DEMO_SCRIPT.read_text(encoding="utf-8"))
    assert found is not None
    home_goals, away_goals, moments = demo_moments
    assert int(found.group(1)) == DEMO_SEED and (int(found.group(2)), int(found.group(3))) == (home_goals, away_goals)
    goal_minutes = [m.minute_label for m in moments if m.kind is MomentKind.GOAL]
    assert MINUTE.findall(found.group(4)) == goal_minutes


def test_demo_match_flags_a_pattern_before_a_goal(demo_moments: tuple[int, int, list[KeyMoment]]) -> None:
    moments = demo_moments[2]
    by_id = {m.moment_id: m for m in moments}
    assert sum(m.kind is MomentKind.TACTICAL_PATTERN for m in moments) <= MAX_FLAGS
    leads = [(goal.match_second - by_id[str(goal.facts["flagged_moment_id"])].match_second) / SECONDS_PER_MINUTE
             for goal in moments if goal.kind is MomentKind.GOAL and "flagged_moment_id" in goal.facts]
    assert any(lead >= MIN_LEAD_MINUTES for lead in leads)


def test_landing_demo_button_uses_the_demo_seed() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    assert f'home: "{DEMO_HOME}", away: "{DEMO_AWAY}", seed: {DEMO_SEED},' in landing
