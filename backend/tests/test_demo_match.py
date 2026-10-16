"""Tests that the documented demo match tells the Tactical Scout story the demo video relies on.

They simulate the demo fixture and compare its scoreline and goal minutes with docs/DEMO_SCRIPT.md.
They also check the flag count, a goal linked to an earlier flag, and that the landing button uses the same seed.
The script's story arc must quote the simulated flagged winner and its offline explanation word for word.
Its timed table must fit the video's pacing; the setup opens All personas before the winner.
The hook or close must call the match seeded and synthetic.
"""

import re
from pathlib import Path

import pytest

from insidegame.agents.context import MomentContext
from insidegame.agents.templates import explanation_template
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
TIME_RANGE = re.compile(r"^\| (\d+):(\d{2})-(\d+):(\d{2}) \|")
TABLE_COLUMNS = 4
MAX_RUNTIME_S = 118
MAX_WORDS_PER_SECOND = 2.7
EXPLANATION_QUOTE_START = "The finish came from"
DEMO_NAMES = ("Kestrel Bay Athletic", "Ironvale United")
MULTIVIEW_OPEN = re.compile(r"open \*\*All personas\*\* at (\d+)'")
SYNTHETIC_CLAIM = "seeded synthetic match"


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


def _flagged_winner(moments: list[KeyMoment]) -> KeyMoment:
    return next(m for m in moments if m.kind is MomentKind.GOAL and "flagged_moment_id" in m.facts
                and m.facts["game_state_change"] == "go_ahead")


def test_demo_script_arc_quotes_the_simulated_flagged_winner(demo_moments: tuple[int, int, list[KeyMoment]]) -> None:
    script = DEMO_SCRIPT.read_text(encoding="utf-8")
    goal = _flagged_winner(demo_moments[2])
    facts = goal.facts
    assert f"Scout flagged {facts['flagged_minute']}: {facts['flagged_summary']}" in script
    assert f"{str(facts['scorer']).upper()} {facts['score_home']}-{facts['score_away']}" in script
    assert f"At {goal.minute_label} {facts['scorer']} scores" in script
    assert f"xG {facts['xg']}" in script


def test_demo_script_quotes_the_offline_winner_explanation_exactly(
        demo_moments: tuple[int, int, list[KeyMoment]]) -> None:
    goal = _flagged_winner(demo_moments[2])
    facts = goal.facts
    home, away = DEMO_NAMES
    context = MomentContext(moment=goal, minute=int(goal.match_second // SECONDS_PER_MINUTE), home_name=home,
                            away_name=away, score_home=int(facts["score_home"]), score_away=int(facts["score_away"]),
                            team_name=home)
    explanation = explanation_template(context)
    why = explanation.why_it_matters
    quote = why[why.index(EXPLANATION_QUOTE_START):]
    script = DEMO_SCRIPT.read_text(encoding="utf-8")
    assert f'"{explanation.headline}"' in script
    assert f'"{quote}"' in script


def test_demo_script_table_is_contiguous_and_paced() -> None:
    rows = [line for line in DEMO_SCRIPT.read_text(encoding="utf-8").splitlines() if TIME_RANGE.match(line)]
    assert rows
    cursor = 0
    for row in rows:
        start_m, start_s, end_m, end_s = (int(g) for g in TIME_RANGE.match(row).groups())
        start, end = start_m * SECONDS_PER_MINUTE + start_s, end_m * SECONDS_PER_MINUTE + end_s
        cells = [c.strip() for c in row.strip().strip("|").split(" | ")]
        assert start == cursor and end > start and len(cells) == TABLE_COLUMNS
        assert len(cells[-1].strip('"').split()) / (end - start) <= MAX_WORDS_PER_SECOND
        cursor = end
    assert cursor <= MAX_RUNTIME_S


def test_demo_script_opens_all_personas_before_the_winner(demo_moments: tuple[int, int, list[KeyMoment]]) -> None:
    script = DEMO_SCRIPT.read_text(encoding="utf-8")
    opened = MULTIVIEW_OPEN.search(script)
    assert opened, "setup must say when to open All personas"
    goal = _flagged_winner(demo_moments[2])
    assert int(opened.group(1)) < int(goal.match_second // SECONDS_PER_MINUTE) + 1
    rows = [line for line in script.splitlines() if TIME_RANGE.match(line)]
    assert SYNTHETIC_CLAIM in rows[0] or SYNTHETIC_CLAIM in rows[-1]
