"""Tests for synthetic dataset rows, the dataset card, and the generator's file output.

They check absolute coordinate normalisation, enrichment fields, reconciliation with the simulation,
and that the generator writes every table and a card consistent with them.
"""

import json
from pathlib import Path

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.datasets.generate import generate
from insidegame.datasets.rows import build_tables
from insidegame.datasets.tracking_rows import DEFAULT_SAMPLE_EVERY, tracking_rows
from insidegame.domain.enums import EventType
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

SQUAD_PLAYERS = 22


def test_rows_reconcile_with_the_simulated_match() -> None:
    result = simulate_match(build_fixture("brookhaven", "ironvale", 5))
    tables = build_tables(result)
    assert len(tables.events) == len(result.events)
    assert len(tables.players) == SQUAD_PLAYERS
    assert tables.match["home_goals"] == result.home_goals
    assert tables.match["home_team_id"] == result.metadata.home.team_id
    assert tables.match["away_team_id"] == result.metadata.away.team_id
    shots = [r for r in tables.events if r["event_type"] == EventType.SHOT.value]
    assert shots and all(isinstance(r["xg"], float) for r in shots)
    assert sum(len(r["moment_kinds"]) for r in tables.events) == len(tables.moments)  # type: ignore[arg-type]


def test_away_coordinates_are_mirrored_into_the_home_frame() -> None:
    result = simulate_match(build_fixture("brookhaven", "ironvale", 5))
    tables = build_tables(result)
    raw = next(e for e in result.events if e.team_id == result.metadata.away.team_id and e.start)
    row = next(r for r in tables.events if r["event_id"] == raw.event_id)
    assert row["start_x"] == round(PITCH_LENGTH_M - raw.start.x, 2)  # type: ignore[union-attr]
    assert row["start_y"] == round(PITCH_WIDTH_M - raw.start.y, 2)  # type: ignore[union-attr]
    assert row["side"] == "away"


def test_generator_writes_all_tables_and_a_consistent_card(tmp_path: Path) -> None:
    counts = generate(2, 1, tmp_path)
    for name in ("matches", "events", "players", "moments", "tracking"):
        lines = (tmp_path / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == counts[name] and json.loads(lines[0])
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert f"| `events.jsonl` | {counts['events']} |" in card and "fictional" in card.lower()
    assert f"| `tracking.jsonl` | {counts['tracking']} |" in card


def test_tracking_rows_sample_every_nth_event_with_all_players_on_the_pitch() -> None:
    result = simulate_match(build_fixture("brookhaven", "ironvale", 5))
    rows = tracking_rows(result)
    assert len(rows) == -(-len(result.events) // DEFAULT_SAMPLE_EVERY)
    assert [r["event_id"] for r in rows] == [e.event_id for e in result.events[::DEFAULT_SAMPLE_EVERY]]
    for row in rows:
        players = row["players"]
        assert len(players) == SQUAD_PLAYERS  # type: ignore[arg-type]
        assert all(0 <= x <= PITCH_LENGTH_M and 0 <= y <= PITCH_WIDTH_M for _, x, y in players)  # type: ignore[union-attr]


def test_full_rate_tracking_keeps_every_frame() -> None:
    result = simulate_match(build_fixture("brookhaven", "ironvale", 5))
    assert len(tracking_rows(result, sample_every=1)) == len(result.events)


def test_event_rows_carry_xt_added_only_for_completed_passes_and_carries() -> None:
    result = simulate_match(build_fixture("brookhaven", "ironvale", 5))
    tables = build_tables(result)
    credited = {EventType.PASS.value, EventType.CARRY.value}
    for row in tables.events:
        assert "xt_added" in row
        expected = row["event_type"] in credited and row["outcome"] == "success"
        assert (row["xt_added"] is not None) == expected
    players_xt = sum(float(p["xt_added"]) for p in tables.players)  # type: ignore[arg-type]
    rows_xt = sum(float(r["xt_added"]) for r in tables.events if r["xt_added"] is not None)  # type: ignore[arg-type]
    assert abs(players_xt - rows_xt) < 0.05
    assert all(p["line_breaking_passes"] == 0 for p in tables.players)
