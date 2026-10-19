"""Pure reader for the subset of TMDL (Tabular Model Definition Language) used by the Fabric semantic model.

It extracts tables, columns with their data types, measures with their DAX expressions, and relationships from
tab-indented TMDL text, and finds every table[column] reference inside a DAX expression. A cross-check then reports
model tables, columns, types, relationship ends, and measure references that disagree with the Delta table specs.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from insidegame.fabric.schema import TMDL_TYPES, FabricSchemaError, TableSpec

INDENT: str = "\t"
QUOTE: str = "'"
TABLE_KEYWORD: str = "table"
COLUMN_KEYWORD: str = "column"
MEASURE_KEYWORD: str = "measure"
RELATIONSHIP_KEYWORD: str = "relationship"
DATA_TYPE_PROPERTY: str = "dataType"
FROM_COLUMN_PROPERTY: str = "fromColumn"
TO_COLUMN_PROPERTY: str = "toColumn"
OBJECT_LEVEL: int = 1
PROPERTY_LEVEL: int = 2
EXPRESSION_LEVEL: int = 3
COLUMN_REF = re.compile(r"(?<![\w'\]])(?:'((?:[^']|'')+)'|([A-Za-z_]\w*))\[([^\]]+)\]")


class TmdlParseError(FabricSchemaError):
    """Raised when TMDL text cannot be read: a bad declaration, name, or column reference."""


@dataclass(frozen=True)
class TmdlColumn:
    """A modelled column with its TMDL data type."""

    table: str
    name: str
    data_type: str


@dataclass(frozen=True)
class TmdlMeasure:
    """A measure on a model table with its DAX expression."""

    table: str
    name: str
    expression: str


@dataclass(frozen=True)
class TmdlRelationship:
    """A relationship from a many-side column to a one-side column."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str


def _level(line: str) -> int:
    return len(line) - len(line.lstrip(INDENT))


def _read_name(text: str) -> tuple[str, str]:
    """Split a possibly quoted TMDL name off the front of text, returning (name, rest)."""
    if not text.startswith(QUOTE):
        match = re.match(r"[^\s=.]+", text)
        if match is None:
            raise TmdlParseError(f"expected a name in '{text}'")
        return match.group(0), text[match.end():]
    index = 1
    while index < len(text):
        if text[index] == QUOTE:
            if text[index + 1:index + 2] == QUOTE:
                index += 2
                continue
            return text[1:index].replace(QUOTE * 2, QUOTE), text[index + 1:]
        index += 1
    raise TmdlParseError(f"unterminated quoted name in '{text}'")


def _keyword_name(stripped: str, keyword: str) -> str | None:
    """Return the declared name when the line starts with the keyword, otherwise None."""
    prefix = keyword + " "
    if not stripped.startswith(prefix):
        return None
    return _read_name(stripped[len(prefix):].strip())[0]


def _measure(stripped: str, table: str, continuation: list[str]) -> TmdlMeasure:
    name, rest = _read_name(stripped[len(MEASURE_KEYWORD) + 1:].strip())
    rest = rest.strip()
    if not rest.startswith("="):
        raise TmdlParseError(f"measure '{name}' has no expression")
    inline = rest[1:].strip()
    expression = "\n".join([inline] if inline else [line.strip() for line in continuation])
    return TmdlMeasure(table, name, expression)


def _continuation(lines: Sequence[str], start: int) -> list[str]:
    """Collect the multi-line expression lines indented below a measure header."""
    block: list[str] = []
    for line in lines[start:]:
        if line.strip() and _level(line) < EXPRESSION_LEVEL:
            break
        block.append(line)
    return block


def parse_table(text: str) -> tuple[list[TmdlColumn], list[TmdlMeasure]]:
    """Read the columns (with dataType) and measures declared in one TMDL table file."""
    lines = text.splitlines()
    table: str | None = None
    columns: list[TmdlColumn] = []
    measures: list[TmdlMeasure] = []
    pending: tuple[str, str] | None = None
    for index, line in enumerate(lines):
        stripped, level = line.strip(), _level(line)
        if level == 0 and (name := _keyword_name(stripped, TABLE_KEYWORD)) is not None:
            table = name
        elif level == OBJECT_LEVEL:
            pending = None
            if table is None:
                continue
            if (name := _keyword_name(stripped, COLUMN_KEYWORD)) is not None:
                pending = (table, name)
            elif stripped.startswith(MEASURE_KEYWORD + " "):
                measures.append(_measure(stripped, table, _continuation(lines, index + 1)))
        elif level == PROPERTY_LEVEL and pending and stripped.startswith(DATA_TYPE_PROPERTY + ":"):
            columns.append(TmdlColumn(*pending, stripped.split(":", 1)[1].strip()))
            pending = None
    return columns, measures


def _column_ref(value: str) -> tuple[str, str]:
    table, rest = _read_name(value.strip())
    if not rest.startswith("."):
        raise TmdlParseError(f"expected table.column, got '{value.strip()}'")
    column, tail = _read_name(rest[1:])
    if tail.strip():
        raise TmdlParseError(f"unexpected text after column reference '{value.strip()}'")
    return table, column


def parse_relationships(text: str) -> list[TmdlRelationship]:
    """Read every relationship's fromColumn and toColumn from TMDL text."""
    relationships: list[TmdlRelationship] = []
    ends: dict[str, tuple[str, str]] = {}
    for line in text.splitlines() + [RELATIONSHIP_KEYWORD + " end"]:
        stripped = line.strip()
        if _level(line) == 0 and stripped.startswith(RELATIONSHIP_KEYWORD + " "):
            if FROM_COLUMN_PROPERTY in ends and TO_COLUMN_PROPERTY in ends:
                relationships.append(TmdlRelationship(*ends[FROM_COLUMN_PROPERTY], *ends[TO_COLUMN_PROPERTY]))
            elif ends:
                raise TmdlParseError("relationship needs both fromColumn and toColumn")
            ends = {}
            continue
        key, separator, value = stripped.partition(":")
        if _level(line) == OBJECT_LEVEL and separator and key in (FROM_COLUMN_PROPERTY, TO_COLUMN_PROPERTY):
            ends[key] = _column_ref(value)
    return relationships


def column_refs(expression: str) -> set[tuple[str, str]]:
    """Return every table[column] reference in a DAX expression (bare [measure] references are ignored)."""
    refs: set[tuple[str, str]] = set()
    for quoted, plain, column in COLUMN_REF.findall(expression):
        refs.add((quoted.replace(QUOTE * 2, QUOTE) if quoted else plain, column))
    return refs


def _column_problems(columns: Sequence[TmdlColumn], tables: Mapping[str, TableSpec]) -> list[str]:
    problems: list[str] = []
    for column in columns:
        spec = tables.get(column.table)
        if spec is None:
            continue
        kinds = {c.name: c.kind for c in spec.columns}
        if column.name not in kinds:
            problems.append(f"column '{column.table}.{column.name}' is not in Delta table '{column.table}'")
        elif column.data_type != TMDL_TYPES[kinds[column.name]]:
            expected = TMDL_TYPES[kinds[column.name]]
            problems.append(f"column '{column.table}.{column.name}' has dataType {column.data_type}, "
                            f"expected {expected}")
    return problems


def model_problems(columns: Sequence[TmdlColumn], measures: Sequence[TmdlMeasure],
                   relationships: Sequence[TmdlRelationship], tables: Mapping[str, TableSpec]) -> list[str]:
    """Cross-check a parsed model against the Delta specs; an empty list means the model is consistent."""
    model_tables = sorted({c.table for c in columns} | {m.table for m in measures})
    problems = [f"model table '{name}' is not a Delta table" for name in model_tables if name not in tables]
    problems.extend(_column_problems(columns, tables))
    modelled = {(c.table, c.name) for c in columns}
    for rel in relationships:
        for table, column in ((rel.from_table, rel.from_column), (rel.to_table, rel.to_column)):
            if (table, column) not in modelled:
                problems.append(f"relationship end '{table}.{column}' is not a modelled column")
    for measure in measures:
        for table, column in sorted(column_refs(measure.expression)):
            if (table, column) not in modelled:
                problems.append(f"measure '{measure.name}' references {table}[{column}], not a modelled column")
    return problems
