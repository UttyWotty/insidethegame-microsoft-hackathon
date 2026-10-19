"""Declarative schemas for the JSON Lines dataset files and the Microsoft Fabric Delta tables built from them.

Source table specs list every column in the exact key order the generator writes, with its kind and nullability,
and render the Spark DDL strings the lakehouse notebook reads with. Delta table specs add the derived columns and
the clubs dimension, and map each column kind to its Spark and TMDL data types; this module performs no I/O.
"""

from dataclasses import dataclass
from enum import Enum


class ColumnKind(Enum):
    """Logical type of a dataset column, independent of the storage engine."""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING_LIST = "string_list"
    JSON_OBJECT = "json_object"
    POSITION_LIST = "position_list"


@dataclass(frozen=True)
class ColumnSpec:
    """One column: its name, logical kind, and whether null is allowed."""

    name: str
    kind: ColumnKind
    nullable: bool


@dataclass(frozen=True)
class TableSpec:
    """One table: its Delta name (equal to the JSONL file stem for source tables) and ordered columns."""

    name: str
    columns: tuple[ColumnSpec, ...]


class FabricSchemaError(Exception):
    """Base error for the Fabric schema layer."""


class UnknownTableError(FabricSchemaError):
    """Raised when a table name is not one of the declared specs."""


S, I, F, B = ColumnKind.STRING, ColumnKind.INT, ColumnKind.FLOAT, ColumnKind.BOOL
NULLABLE: bool = True
REQUIRED: bool = False


def _cols(*specs: tuple[str, ColumnKind, bool]) -> tuple[ColumnSpec, ...]:
    return tuple(ColumnSpec(name, kind, nullable) for name, kind, nullable in specs)


def _required(kind: ColumnKind, *names: str) -> tuple[tuple[str, ColumnKind, bool], ...]:
    return tuple((name, kind, REQUIRED) for name in names)


MATCHES = TableSpec("matches", _cols(
    *_required(S, "match_id"), *_required(I, "seed"),
    *_required(S, "competition", "venue", "home", "away", "home_team_id", "away_team_id", "home_style",
               "away_style"),
    *_required(I, "home_goals", "away_goals", "events"),
    *_required(F, "home_possession_pct", "home_xg", "away_xg"), *_required(I, "key_moments"),
))

EVENTS = TableSpec("events", _cols(
    *_required(S, "event_id", "match_id"), *_required(I, "sequence", "period"), ("match_second", F, REQUIRED),
    ("minute", I, REQUIRED), ("event_type", S, REQUIRED), ("team_id", S, NULLABLE), ("player_id", S, NULLABLE),
    ("possession_id", I, REQUIRED), ("outcome", S, NULLABLE), ("receiver_id", S, NULLABLE),
    ("opponent_id", S, NULLABLE), ("under_pressure", B, REQUIRED), ("length_m", F, NULLABLE),
    ("ball_speed_kmh", F, NULLABLE), ("shot_result", S, NULLABLE), ("seed", I, REQUIRED), ("side", S, NULLABLE),
    ("minute_label", S, REQUIRED), ("start_x", F, NULLABLE), ("start_y", F, NULLABLE), ("end_x", F, NULLABLE),
    ("end_y", F, NULLABLE), *_required(I, "score_home", "score_away"), ("xg", F, NULLABLE),
    ("pass_difficulty", F, NULLABLE), ("momentum", F, REQUIRED), ("rhythm_state", S, REQUIRED),
    ("xt_added", F, NULLABLE), ("moment_kinds", ColumnKind.STRING_LIST, REQUIRED),
))

PLAYERS = TableSpec("players", _cols(
    ("match_id", S, REQUIRED),
    *_required(I, "passes_attempted", "passes_completed", "progressive_passes", "final_third_entries", "shots",
               "shots_on_target", "goals"),
    *_required(F, "xg", "max_shot_speed_kmh"), ("carries", I, REQUIRED), ("carry_distance_m", F, REQUIRED),
    *_required(I, "tackles", "interceptions", "pressures", "fouls", "saves"), ("xt_added", F, REQUIRED),
    *_required(I, "line_breaking_passes", "opponents_bypassed"), *_required(S, "player_id", "team_id", "name"),
    *_required(F, "pass_accuracy", "avg_pass_difficulty"), ("position", S, REQUIRED), ("shirt_number", I, REQUIRED),
))

MOMENTS = TableSpec("moments", _cols(
    *_required(S, "match_id", "moment_id", "kind"), ("period", I, REQUIRED), ("match_second", F, REQUIRED),
    ("minute", I, REQUIRED), ("minute_label", S, REQUIRED), ("importance", F, REQUIRED), ("team_id", S, NULLABLE),
    ("player_ids", ColumnKind.STRING_LIST, REQUIRED), ("event_ids", ColumnKind.STRING_LIST, REQUIRED),
    ("facts", ColumnKind.JSON_OBJECT, REQUIRED),
))

TRACKING = TableSpec("tracking", _cols(
    *_required(S, "match_id", "event_id"), *_required(I, "sequence", "period"), ("match_second", F, REQUIRED),
    *_required(F, "ball_x", "ball_y"), ("players", ColumnKind.POSITION_LIST, REQUIRED),
    ("sprint_player_id", S, NULLABLE), ("sprint_kmh", F, NULLABLE),
))

SOURCE_TABLES: dict[str, TableSpec] = {spec.name: spec for spec in (MATCHES, EVENTS, PLAYERS, MOMENTS, TRACKING)}

DERIVED_COLUMNS: dict[str, tuple[ColumnSpec, ...]] = {
    "events": (ColumnSpec("phase", S, REQUIRED),),
    "moments": (ColumnSpec("scout_pattern", S, NULLABLE),),
}

CLUBS_TABLE: TableSpec = TableSpec("clubs", _cols(*_required(S, "team_id", "club_name", "style")))

PHASE_MINUTES: int = 15
PHASE_LABELS: tuple[str, ...] = ("00-15", "15-30", "30-45", "45-60", "60-75", "75-90+")

SPARK_TYPES: dict[ColumnKind, str] = {
    ColumnKind.STRING: "STRING",
    ColumnKind.INT: "BIGINT",
    ColumnKind.FLOAT: "DOUBLE",
    ColumnKind.BOOL: "BOOLEAN",
    ColumnKind.STRING_LIST: "ARRAY<STRING>",
    ColumnKind.JSON_OBJECT: "STRING",
    ColumnKind.POSITION_LIST: "ARRAY<ARRAY<STRING>>",
}

TMDL_TYPES: dict[ColumnKind, str] = {
    ColumnKind.STRING: "string",
    ColumnKind.INT: "int64",
    ColumnKind.FLOAT: "double",
    ColumnKind.BOOL: "boolean",
    ColumnKind.STRING_LIST: "string",
    ColumnKind.JSON_OBJECT: "string",
    ColumnKind.POSITION_LIST: "string",
}


def source_table(name: str) -> TableSpec:
    """Return the source spec for a JSONL file stem, raising UnknownTableError for any other name."""
    try:
        return SOURCE_TABLES[name]
    except KeyError:
        raise UnknownTableError(f"unknown source table '{name}'") from None


def spark_ddl(name: str) -> str:
    """Render the Spark DDL schema string for a source table, columns in file order."""
    return ", ".join(f"{column.name} {SPARK_TYPES[column.kind]}" for column in source_table(name).columns)


def delta_tables() -> dict[str, TableSpec]:
    """Return every Delta table: source tables plus their derived columns, followed by the clubs dimension.

    List and object kinds are kept on the spec so the TMDL mapping knows they are stored as JSON strings.
    """
    tables = {
        name: TableSpec(name, spec.columns + DERIVED_COLUMNS.get(name, ())) for name, spec in SOURCE_TABLES.items()
    }
    tables[CLUBS_TABLE.name] = CLUBS_TABLE
    return tables
