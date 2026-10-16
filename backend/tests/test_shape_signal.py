"""Tests that shape_shift moments are real signal in simulated matches and that the demo match tells the shape story.

They drive TrackingModel and MatchAnalyzer exactly as the live service does (positions from before each event) over
twenty seeds of the demo pairing, then check the shift rate, recall on late protect-the-lead spells, and that space
control moves with the line. The demo seed must hold a dropped shift by the leader that docs/DEMO_SCRIPT.md names.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from threat_helpers import TrackedMatch, analyse_with_tracking

from insidegame.analytics.moments import FactValue, KeyMoment, MomentKind
from insidegame.simulation.probabilities import PROTECT_START_SECOND
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SCRIPT = REPO_ROOT / "docs" / "DEMO_SCRIPT.md"
SHAPE_LINE = re.compile(r"Shape shift at (\d+(?:\+\d+)?')")
SEEDS = range(1, 21)
FINAL_PERIOD = 2
MIN_PROTECT_EPISODE_S = 600.0
RATE_RANGE = (0.5, 2.0)
MIN_RECALL = 0.5
MIN_CONTROL_AGREEMENT = 0.9


@dataclass(frozen=True)
class Episode:
    """A team leading continuously in the final period from at least 70' for MIN_PROTECT_EPISODE_S or more."""

    team_id: str
    start: float
    end: float


def _num(value: FactValue) -> float:
    return float(str(value))


def _shifts(match: TrackedMatch) -> list[KeyMoment]:
    return [m for m in match.analyzer.moments if m.kind is MomentKind.SHAPE_SHIFT]


def _episodes(match: TrackedMatch) -> list[Episode]:
    """Contiguous late leads, measured on the event clock."""
    found: list[Episode] = []
    for team in (match.result.metadata.home, match.result.metadata.away):
        sign = 1 if team is match.result.metadata.home else -1
        start: float | None = None
        last = 0.0
        for event in match.result.events:
            if event.period != FINAL_PERIOD or event.match_second < PROTECT_START_SECOND:
                continue
            leading = sign * (event.score_home - event.score_away) > 0
            if leading and start is None:
                start = event.match_second
            if not leading and start is not None:
                found.append(Episode(team.team_id, start, event.match_second))
                start = None
            last = event.match_second
        if start is not None:
            found.append(Episode(team.team_id, start, last))
    return [e for e in found if e.end - e.start >= MIN_PROTECT_EPISODE_S]


@pytest.fixture(scope="module")
def matches() -> list[TrackedMatch]:
    return [analyse_with_tracking(DEMO_HOME, DEMO_AWAY, seed) for seed in SEEDS]


def test_shift_rate_is_between_half_and_two_per_match(matches: list[TrackedMatch]) -> None:
    rate = sum(len(_shifts(m)) for m in matches) / len(matches)
    assert RATE_RANGE[0] <= rate <= RATE_RANGE[1]


def test_most_late_protect_spells_produce_a_dropped_shift_by_the_leader(matches: list[TrackedMatch]) -> None:
    episodes = hits = 0
    for match in matches:
        shifts = _shifts(match)
        for episode in _episodes(match):
            episodes += 1
            hits += any(s.team_id == episode.team_id and s.facts["direction"] == "dropped"
                        and s.period == FINAL_PERIOD and episode.start <= s.match_second <= episode.end
                        for s in shifts)
    assert episodes and hits / episodes >= MIN_RECALL


def test_space_control_moves_with_the_line(matches: list[TrackedMatch]) -> None:
    shifts = [s for m in matches for s in _shifts(m)]
    assert shifts
    agree = sum((_num(s.facts["control_after_pct"]) < _num(s.facts["control_before_pct"]))
                == (s.facts["direction"] == "dropped") for s in shifts)
    assert agree / len(shifts) >= MIN_CONTROL_AGREEMENT


def test_demo_match_has_the_scripted_dropped_shift_by_the_leader() -> None:
    match = analyse_with_tracking(DEMO_HOME, DEMO_AWAY, DEMO_SEED)
    dropped = [s for s in _shifts(match) if s.facts["direction"] == "dropped" and _num(s.facts["goal_difference"]) > 0]
    assert dropped
    shift = dropped[0]
    assert shift.facts["trigger"] == "went_ahead"
    assert _num(shift.facts["control_after_pct"]) < _num(shift.facts["control_before_pct"])
    found = SHAPE_LINE.search(DEMO_SCRIPT.read_text(encoding="utf-8"))
    assert found is not None and found.group(1) == shift.minute_label
