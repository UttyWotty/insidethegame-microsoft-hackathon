"""Tests for the Fabric lakehouse notebook, the TMDL semantic model, and the offline check command.

They assert the committed notebook parses and carries the exact Spark schemas, and that the committed TMDL model
has the required measures and relationships and agrees with the Delta table specs. Mutated TMDL and notebook text
prove each drift is reported, and the command line is exercised for its OK and missing-input exit codes.
"""

import ast
import json
from pathlib import Path

import pytest

from insidegame.fabric.check import main
from insidegame.fabric.notebook import code_cells, notebook_problems, notebook_schemas, strip_magics
from insidegame.fabric.schema import SOURCE_TABLES, delta_tables, spark_ddl
from insidegame.fabric.tmdl import (
    TmdlColumn,
    TmdlMeasure,
    TmdlParseError,
    TmdlRelationship,
    column_refs,
    model_problems,
    parse_relationships,
    parse_table,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC = REPO_ROOT / "fabric"
SAMPLE = REPO_ROOT / "data" / "sample"
NOTEBOOK = FABRIC / "notebooks" / "load_lakehouse.ipynb"
DEFINITION = FABRIC / "InsideTheGame.SemanticModel" / "definition"
WRITTEN_TABLES = ("matches", "clubs", "events", "players", "moments", "tracking")
REQUIRED_MEASURES = {
    "Goals", "Expected Goals", "Goals minus xG", "Shots", "Pass Accuracy %", "Avg Pass Difficulty", "xT Added",
    "Avg Momentum", "Pass Share %", "Scout Flags",
}
REQUIRED_RELATIONSHIPS = {
    TmdlRelationship(many, column, one, column)
    for many in ("events", "players", "moments")
    for one, column in (("matches", "match_id"), ("clubs", "team_id"))
}


def _notebook_text() -> str:
    return NOTEBOOK.read_text(encoding="utf-8")


def _model() -> tuple[list[TmdlColumn], list[TmdlMeasure], list[TmdlRelationship]]:
    columns: list[TmdlColumn] = []
    measures: list[TmdlMeasure] = []
    for path in sorted((DEFINITION / "tables").glob("*.tmdl")):
        table_columns, table_measures = parse_table(path.read_text(encoding="utf-8"))
        columns += table_columns
        measures += table_measures
    relationships = parse_relationships((DEFINITION / "relationships.tmdl").read_text(encoding="utf-8"))
    return columns, measures, relationships


def _problems_for_events_text(text: str) -> list[str]:
    columns, measures, relationships = _model()
    columns = [c for c in columns if c.table != "events"]
    measures = [m for m in measures if m.table != "events"]
    extra_columns, extra_measures = parse_table(text)
    return model_problems(columns + extra_columns, measures + extra_measures, relationships, delta_tables())


def _events_text() -> str:
    return (DEFINITION / "tables" / "events.tmdl").read_text(encoding="utf-8")


def test_notebook_is_valid_json_with_parsable_code_cells() -> None:
    json.loads(_notebook_text())
    sources = code_cells(_notebook_text())
    assert sources
    for source in sources:
        ast.parse(strip_magics(source))


def test_notebook_schemas_equal_the_python_source_of_truth() -> None:
    schemas = notebook_schemas(code_cells(_notebook_text()))
    assert schemas == {name: spark_ddl(name) for name in SOURCE_TABLES}


def test_notebook_writes_all_six_delta_tables() -> None:
    saving = "\n".join(source for source in code_cells(_notebook_text()) if "saveAsTable" in source)
    for name in WRITTEN_TABLES:
        assert f'"{name}"' in saving
    assert notebook_problems(_notebook_text()) == []


def test_notebook_strip_magics_drops_only_magic_lines() -> None:
    assert strip_magics("%pip install x\nx = 1\n  %%sql") == "x = 1"


def test_notebook_drift_and_breakage_are_reported() -> None:
    notebook = json.loads(_notebook_text())
    for cell in notebook["cells"]:
        cell["source"] = [line.replace("seed BIGINT", "seed STRING") for line in cell["source"]]
        cell["source"] = [line.replace('save(tables["tracking"], "tracking")', "") for line in cell["source"]]
    notebook["cells"].append({"cell_type": "code", "source": ["def broken(:\n"]})
    problems = notebook_problems(json.dumps(notebook))
    assert any("code cell 6 does not parse" in p for p in problems)
    assert "SOURCE_SCHEMAS['matches'] differs from spark_ddl('matches')" in problems
    assert "table 'tracking' is not written with saveAsTable" in problems


@pytest.mark.parametrize("text", ["{not json", "[]", '{"cells": 3}'])
def test_notebook_unreadable_text_is_one_problem(text: str) -> None:
    assert len(notebook_problems(text)) == 1


def test_tmdl_model_is_consistent_with_the_delta_tables() -> None:
    columns, measures, relationships = _model()
    assert columns and measures and relationships
    assert model_problems(columns, measures, relationships, delta_tables()) == []


def test_tmdl_model_has_the_required_measures_and_relationships() -> None:
    _, measures, relationships = _model()
    assert {m.name for m in measures} >= REQUIRED_MEASURES
    assert set(relationships) >= REQUIRED_RELATIONSHIPS
    assert len(relationships) == len(REQUIRED_RELATIONSHIPS)


def test_tmdl_model_leaves_tracking_out() -> None:
    columns, _, _ = _model()
    assert {c.table for c in columns} == {"matches", "clubs", "events", "players", "moments"}


def test_tmdl_parses_multi_line_and_quoted_measures() -> None:
    measures = {m.name: m for m in parse_table(_events_text())[1]}
    share = measures["Pass Share %"].expression
    assert share.startswith("VAR TeamPasses") and "REMOVEFILTERS(clubs)" in share
    assert column_refs(share) == {("events", "event_type")}


def test_tmdl_column_refs_handle_quoted_tables_and_ignore_measure_refs() -> None:
    expression = "[Goals] - SUM('my table'[x]) + AVERAGE(events[xg]) + 'it''s'[y]"
    assert column_refs(expression) == {("my table", "x"), ("events", "xg"), ("it's", "y")}


def test_tmdl_unknown_column_is_one_problem() -> None:
    text = _events_text() + "\n\tcolumn nope\n\t\tdataType: string\n\t\tsourceColumn: nope\n"
    problems = _problems_for_events_text(text)
    assert problems == ["column 'events.nope' is not in Delta table 'events'"]


def test_tmdl_wrong_data_type_is_one_problem() -> None:
    text = _events_text().replace("column xg\n\t\tdataType: double", "column xg\n\t\tdataType: int64")
    problems = _problems_for_events_text(text)
    assert problems == ["column 'events.xg' has dataType int64, expected double"]


def test_tmdl_measure_referencing_a_missing_column_is_one_problem() -> None:
    text = _events_text() + "\n\tmeasure Broken = SUM(events[nope])\n"
    problems = _problems_for_events_text(text)
    assert problems == ["measure 'Broken' references events[nope], not a modelled column"]


def test_tmdl_relationship_to_a_missing_column_is_one_problem() -> None:
    columns, measures, relationships = _model()
    broken = [*relationships, TmdlRelationship("events", "player_id", "players", "nope")]
    problems = model_problems(columns, measures, broken, delta_tables())
    assert problems == ["relationship end 'players.nope' is not a modelled column"]


def test_tmdl_unknown_model_table_is_reported() -> None:
    problems = model_problems([TmdlColumn("ghosts", "id", "string")], [], [], delta_tables())
    assert problems == ["model table 'ghosts' is not a Delta table"]


@pytest.mark.parametrize("text", [
    "relationship r\n\tfromColumn: events.match_id\n",
    "relationship r\n\tfromColumn: events\n\ttoColumn: matches.match_id\n",
    "relationship r\n\tfromColumn: 'events.match_id\n\ttoColumn: matches.match_id\n",
])
def test_tmdl_malformed_relationship_raises_a_parse_error(text: str) -> None:
    with pytest.raises(TmdlParseError):
        parse_relationships(text)


def test_tmdl_measure_without_expression_raises_a_parse_error() -> None:
    with pytest.raises(TmdlParseError):
        parse_table("table events\n\tmeasure Broken\n")


def test_cli_validates_the_committed_sample_and_model(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--data", str(SAMPLE), "--fabric", str(FABRIC)]) == 0
    output = capsys.readouterr().out.strip().splitlines()
    assert len(output) == 1 and output[0].startswith("OK: 5 tables, 5985 rows,")


def test_cli_reports_missing_inputs_without_raising(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--data", str(tmp_path / "none"), "--fabric", str(tmp_path / "none")]) == 1
    output = capsys.readouterr().out
    assert output.count("missing:") == 3


def test_cli_reports_bad_rows_with_file_and_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in SOURCE_TABLES:
        (tmp_path / f"{name}.jsonl").write_text((SAMPLE / f"{name}.jsonl").read_text(encoding="utf-8"),
                                                encoding="utf-8")
    (tmp_path / "matches.jsonl").write_text("{broken\n", encoding="utf-8")
    (tmp_path / "players.jsonl").write_bytes(b"\xff\xfe")
    assert main(["--data", str(tmp_path), "--fabric", str(FABRIC)]) == 1
    output = capsys.readouterr().out
    assert f"{tmp_path / 'matches.jsonl'}:1: invalid JSON" in output
    assert f"{tmp_path / 'players.jsonl'}:0: cannot read:" in output


def test_cli_caps_the_number_of_reported_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in SOURCE_TABLES:
        (tmp_path / f"{name}.jsonl").write_text("{}\n" * 30, encoding="utf-8")
    assert main(["--data", str(tmp_path), "--fabric", str(FABRIC)]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 51 and lines[-1].startswith("... and ")
