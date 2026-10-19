"""Pure validation of JSON Lines dataset rows against the declared Fabric source table specs.

Each row is checked for missing and unexpected columns, nulls in non-nullable columns, and values whose JSON type
does not match the column kind (booleans never count as numbers). Problems are returned as values with a table
name and 1-based line number, never raised, so a caller can report every problem in a file at once.
"""

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from insidegame.fabric.schema import ColumnKind, TableSpec

POSITION_ITEMS: int = 3
NO_ROWS_LINE: int = 0
NO_ROWS_MESSAGE: str = "no rows"
INVALID_JSON_MESSAGE: str = "invalid JSON"
NOT_AN_OBJECT_MESSAGE: str = "row is not a JSON object"


@dataclass(frozen=True)
class SchemaProblem:
    """One schema violation: the table, the 1-based JSONL line, and a readable message."""

    table: str
    line: int
    message: str


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_position(item: object) -> bool:
    return (isinstance(item, list) and len(item) == POSITION_ITEMS and isinstance(item[0], str)
            and _is_number(item[1]) and _is_number(item[2]))


def _is_position_list(value: object) -> bool:
    return isinstance(value, list) and all(_is_position(item) for item in value)


TYPE_CHECKS: dict[ColumnKind, Callable[[object], bool]] = {
    ColumnKind.STRING: lambda value: isinstance(value, str),
    ColumnKind.INT: _is_int,
    ColumnKind.FLOAT: _is_number,
    ColumnKind.BOOL: lambda value: isinstance(value, bool),
    ColumnKind.STRING_LIST: _is_string_list,
    ColumnKind.JSON_OBJECT: lambda value: isinstance(value, dict),
    ColumnKind.POSITION_LIST: _is_position_list,
}


def validate_row(spec: TableSpec, row: Mapping[str, object], line: int) -> list[SchemaProblem]:
    """Return every problem with one parsed row; an empty list means the row matches the spec."""
    problems: list[SchemaProblem] = []
    declared = {column.name for column in spec.columns}
    for column in spec.columns:
        if column.name not in row:
            problems.append(SchemaProblem(spec.name, line, f"missing column '{column.name}'"))
            continue
        value = row[column.name]
        if value is None:
            if not column.nullable:
                problems.append(SchemaProblem(spec.name, line, f"column '{column.name}' is null but not nullable"))
        elif not TYPE_CHECKS[column.kind](value):
            message = f"column '{column.name}' expected {column.kind.value}, got {type(value).__name__}"
            problems.append(SchemaProblem(spec.name, line, message))
    for name in row:
        if name not in declared:
            problems.append(SchemaProblem(spec.name, line, f"unexpected column '{name}'"))
    return problems


def validate_lines(spec: TableSpec, lines: Iterable[str]) -> list[SchemaProblem]:
    """Parse and validate JSON Lines text; blank lines are skipped and an input with no rows is a problem."""
    problems: list[SchemaProblem] = []
    rows = 0
    for number, text in enumerate(lines, start=1):
        if not text.strip():
            continue
        rows += 1
        try:
            row = json.loads(text)
        except (ValueError, RecursionError):
            problems.append(SchemaProblem(spec.name, number, INVALID_JSON_MESSAGE))
            continue
        if not isinstance(row, dict):
            problems.append(SchemaProblem(spec.name, number, NOT_AN_OBJECT_MESSAGE))
            continue
        problems.extend(validate_row(spec, row, number))
    if rows == 0:
        problems.append(SchemaProblem(spec.name, NO_ROWS_LINE, NO_ROWS_MESSAGE))
    return problems
