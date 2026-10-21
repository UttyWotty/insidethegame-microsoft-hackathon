"""Command-line check that a dataset folder and the fabric/ folder agree with the Python schema source of truth.

Run it from backend/ with the --data and --fabric options (defaults: ../data/sample and ../fabric).
It validates every JSONL source file, the lakehouse notebook, and the TMDL semantic model, printing one
`<file>:<line>: <message>` line per problem and exiting 1, or a single OK summary line and exiting 0.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from insidegame.fabric.notebook import notebook_problems
from insidegame.fabric.schema import SOURCE_TABLES, delta_tables, source_table
from insidegame.fabric.tmdl import (
    TmdlColumn,
    TmdlMeasure,
    TmdlParseError,
    TmdlRelationship,
    model_problems,
    parse_relationships,
    parse_table,
)
from insidegame.fabric.validate import validate_lines

DEFAULT_DATA: Path = Path("../data/sample")
DEFAULT_FABRIC: Path = Path("../fabric")
NOTEBOOK_PATH: Path = Path("notebooks/load_lakehouse.ipynb")
MODEL_DEFINITION: Path = Path("InsideTheGame.SemanticModel/definition")
TABLES_DIR: str = "tables"
RELATIONSHIPS_FILE: str = "relationships.tmdl"
TMDL_GLOB: str = "*.tmdl"
JSONL_SUFFIX: str = ".jsonl"
ENCODING: str = "utf-8"
NO_LINE: int = 0
MAX_REPORTED: int = 50
EXIT_OK: int = 0
EXIT_PROBLEMS: int = 1


@dataclass
class CheckResult:
    """Problems found plus the counts reported in the OK summary."""

    problems: list[str] = field(default_factory=list)
    rows: int = 0
    columns: int = 0
    measures: int = 0


def _problem(path: Path, line: int, message: str) -> str:
    return f"{path}:{line}: {message}"


def _read(path: Path, result: CheckResult) -> str | None:
    """Read a text file, recording a missing or unreadable file as a problem instead of raising."""
    if not path.is_file():
        result.problems.append(f"missing: {path}")
        return None
    try:
        return path.read_text(encoding=ENCODING)
    except (OSError, UnicodeDecodeError) as error:
        result.problems.append(_problem(path, NO_LINE, f"cannot read: {error}"))
        return None


def check_data(data: Path, result: CheckResult) -> None:
    """Validate every source table's JSONL file in the data directory."""
    if not data.is_dir():
        result.problems.append(f"missing: {data}")
        return
    for name in SOURCE_TABLES:
        path = data / f"{name}{JSONL_SUFFIX}"
        text = _read(path, result)
        if text is None:
            continue
        lines = text.splitlines()
        result.rows += sum(1 for line in lines if line.strip())
        result.problems += [_problem(path, p.line, p.message) for p in validate_lines(source_table(name), lines)]


def check_notebook(fabric: Path, result: CheckResult) -> None:
    """Check the lakehouse notebook parses and matches the declared schemas."""
    path = fabric / NOTEBOOK_PATH
    text = _read(path, result)
    if text is not None:
        result.problems += [_problem(path, NO_LINE, message) for message in notebook_problems(text)]


def _parse_model(definition: Path, result: CheckResult) -> tuple[
        list[TmdlColumn], list[TmdlMeasure], list[TmdlRelationship]]:
    columns: list[TmdlColumn] = []
    measures: list[TmdlMeasure] = []
    relationships: list[TmdlRelationship] = []
    table_files = sorted((definition / TABLES_DIR).glob(TMDL_GLOB))
    if not table_files:
        result.problems.append(f"missing: {definition / TABLES_DIR / TMDL_GLOB}")
    for path in [*table_files, definition / RELATIONSHIPS_FILE]:
        text = _read(path, result)
        if text is None:
            continue
        try:
            if path.name == RELATIONSHIPS_FILE:
                relationships += parse_relationships(text)
            else:
                table_columns, table_measures = parse_table(text)
                columns += table_columns
                measures += table_measures
        except TmdlParseError as error:
            result.problems.append(_problem(path, NO_LINE, str(error)))
    return columns, measures, relationships


def check_model(fabric: Path, result: CheckResult) -> None:
    """Parse the TMDL semantic model and cross-check it against the Delta table specs."""
    definition = fabric / MODEL_DEFINITION
    if not definition.is_dir():
        result.problems.append(f"missing: {definition}")
        return
    columns, measures, relationships = _parse_model(definition, result)
    result.columns, result.measures = len(columns), len(measures)
    problems = model_problems(columns, measures, relationships, delta_tables())
    result.problems += [_problem(definition, NO_LINE, message) for message in problems]


def run_checks(data: Path, fabric: Path) -> CheckResult:
    """Run the data, notebook, and model checks and return the combined result."""
    result = CheckResult()
    check_data(data, result)
    check_notebook(fabric, result)
    check_model(fabric, result)
    return result


def report(result: CheckResult) -> list[str]:
    """Render the result as output lines: capped problem lines, or one OK summary line."""
    if not result.problems:
        return [f"OK: {len(SOURCE_TABLES)} tables, {result.rows} rows, {result.columns} model columns, "
                f"{result.measures} measures"]
    lines = result.problems[:MAX_REPORTED]
    hidden = len(result.problems) - len(lines)
    if hidden > 0:
        lines.append(f"... and {hidden} more problems")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run every check, print the report, and return the exit code."""
    parser = argparse.ArgumentParser(description="Check the dataset and Fabric artifacts against the schemas.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="JSONL dataset folder")
    parser.add_argument("--fabric", type=Path, default=DEFAULT_FABRIC, help="fabric/ artifacts folder")
    args = parser.parse_args(argv)
    result = run_checks(args.data, args.fabric)
    for line in report(result):
        print(line)
    return EXIT_PROBLEMS if result.problems else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
