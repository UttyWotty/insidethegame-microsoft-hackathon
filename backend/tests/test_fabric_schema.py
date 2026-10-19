"""Tests for the Fabric source schemas, Spark DDL rendering, Delta table specs, and the JSONL row validator.

The happy path validates every committed sample row, proving the declared schemas match what the generator writes.
Each error path (missing, unexpected, wrong type, null, malformed positions, invalid JSON, empty input, unknown
table) is exercised on its own so a regression points straight at the broken rule.
"""

import json
from pathlib import Path

import pytest

from insidegame.datasets.generate import generate
from insidegame.fabric.schema import (
    CLUBS_TABLE,
    PHASE_LABELS,
    SOURCE_TABLES,
    SPARK_TYPES,
    TMDL_TYPES,
    ColumnKind,
    UnknownTableError,
    delta_tables,
    source_table,
    spark_ddl,
)
from insidegame.fabric.validate import SchemaProblem, validate_lines, validate_row
from insidegame.simulation.roster import CLUB_PRESETS

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "data" / "sample"


def _first_row(name: str) -> dict[str, object]:
    with (SAMPLE / f"{name}.jsonl").open(encoding="utf-8") as handle:
        return json.loads(handle.readline())


def _messages(problems: list[SchemaProblem]) -> list[str]:
    return [problem.message for problem in problems]


@pytest.mark.parametrize("name", list(SOURCE_TABLES))
def test_every_committed_sample_row_matches_its_schema(name: str) -> None:
    lines = (SAMPLE / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    assert validate_lines(source_table(name), lines) == []


@pytest.mark.parametrize("name", list(SOURCE_TABLES))
def test_source_columns_follow_the_file_key_order(name: str) -> None:
    assert [c.name for c in source_table(name).columns] == list(_first_row(name))


def test_every_kind_maps_to_a_spark_and_a_tmdl_type() -> None:
    assert set(SPARK_TYPES) == set(ColumnKind) == set(TMDL_TYPES)


def test_spark_ddl_renders_columns_in_order() -> None:
    ddl = spark_ddl("matches")
    assert ddl.startswith("match_id STRING, seed BIGINT, competition STRING")
    assert "home_team_id STRING, away_team_id STRING" in ddl
    assert spark_ddl("tracking").endswith("players ARRAY<ARRAY<STRING>>, sprint_player_id STRING, sprint_kmh DOUBLE")
    assert "facts STRING" in spark_ddl("moments")


def test_delta_tables_add_derived_columns_and_the_clubs_dimension() -> None:
    tables = delta_tables()
    assert list(tables) == [*SOURCE_TABLES, CLUBS_TABLE.name]
    assert [c.name for c in tables["events"].columns][-1] == "phase"
    scout = tables["moments"].columns[-1]
    assert scout.name == "scout_pattern" and scout.nullable
    assert [c.name for c in tables["clubs"].columns] == ["team_id", "club_name", "style"]
    assert len(PHASE_LABELS) == 6


def test_unknown_table_raises_a_domain_error() -> None:
    with pytest.raises(UnknownTableError):
        source_table("nope")
    with pytest.raises(UnknownTableError):
        spark_ddl("nope")


def test_missing_column_is_reported() -> None:
    row = _first_row("players")
    del row["xg"]
    assert _messages(validate_row(source_table("players"), row, 3)) == ["missing column 'xg'"]


def test_unexpected_column_is_reported() -> None:
    row = _first_row("matches") | {"foo": 1}
    assert _messages(validate_row(source_table("matches"), row, 1)) == ["unexpected column 'foo'"]


def test_wrong_type_is_reported() -> None:
    row = _first_row("matches") | {"seed": "1"}
    assert _messages(validate_row(source_table("matches"), row, 1)) == ["column 'seed' expected int, got str"]


@pytest.mark.parametrize("column", ["seed", "home_xg"])
def test_wrong_type_bool_is_not_a_number(column: str) -> None:
    row = _first_row("matches") | {column: True}
    problems = validate_row(source_table("matches"), row, 1)
    assert len(problems) == 1 and "got bool" in problems[0].message


def test_wrong_type_int_is_accepted_for_float_but_float_not_for_int() -> None:
    spec = source_table("matches")
    assert validate_row(spec, _first_row("matches") | {"home_xg": 1}, 1) == []
    assert len(validate_row(spec, _first_row("matches") | {"seed": 1.5}, 1)) == 1


def test_wrong_type_for_list_and_object_kinds() -> None:
    spec = source_table("moments")
    assert len(validate_row(spec, _first_row("moments") | {"player_ids": ["a", 1]}, 1)) == 1
    assert len(validate_row(spec, _first_row("moments") | {"facts": []}, 1)) == 1


def test_null_in_non_nullable_column_is_reported() -> None:
    row = _first_row("events") | {"match_id": None}
    assert _messages(validate_row(source_table("events"), row, 2)) == ["column 'match_id' is null but not nullable"]


def test_null_in_nullable_column_is_accepted() -> None:
    row = _first_row("events") | {"xg": None, "team_id": None}
    assert validate_row(source_table("events"), row, 1) == []


@pytest.mark.parametrize("players", [
    [["brk-01", 1.0]],
    [["brk-01", "1.0", 2.0]],
    [[1, 1.0, 2.0]],
    [["brk-01", True, 2.0]],
    ["brk-01"],
    {"brk-01": [1.0, 2.0]},
])
def test_malformed_position_list_is_reported(players: object) -> None:
    row = _first_row("tracking") | {"players": players}
    assert _messages(validate_row(source_table("tracking"), row, 1)) == [
        "column 'players' expected position_list, got " + type(players).__name__]


def test_invalid_json_line_is_reported_with_its_line_number() -> None:
    good = json.dumps(_first_row("matches"))
    problems = validate_lines(source_table("matches"), [good, "{not json", "[1, 2]"])
    assert problems == [SchemaProblem("matches", 2, "invalid JSON"),
                        SchemaProblem("matches", 3, "row is not a JSON object")]


def test_empty_input_is_reported_as_no_rows() -> None:
    assert _messages(validate_lines(source_table("events"), [])) == ["no rows"]
    assert _messages(validate_lines(source_table("events"), ["", "  "])) == ["no rows"]


FRESH_START_SEED = 500


def test_freshly_generated_rows_match_their_schemas_and_give_unique_clubs(tmp_path: Path) -> None:
    """Rows from seeds outside the committed sample validate, and each club id maps to one name and style."""
    generate(len(CLUB_PRESETS), FRESH_START_SEED, tmp_path)
    for name, spec in SOURCE_TABLES.items():
        lines = (tmp_path / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        assert validate_lines(spec, lines) == []
    matches = [json.loads(line) for line in (tmp_path / "matches.jsonl").read_text(encoding="utf-8").splitlines()]
    clubs = {(m[f"{side}_team_id"], m[side], m[f"{side}_style"]) for m in matches for side in ("home", "away")}
    assert len({team_id for team_id, _, _ in clubs}) == len(clubs) == len(CLUB_PRESETS)
