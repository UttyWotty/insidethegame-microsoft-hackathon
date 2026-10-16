"""Tests for the pure expected threat (xT) model, the committed grid, and the lookup.

They cover cell edges and clamping, value iteration against a closed-form chain, convergence failure, symmetrisation,
tackle counting, byte-for-byte regeneration of the committed grid, and the import direction of the new modules.
Small hand-built counts have closed-form answers, so the solver is checked without simulating any match.
"""

import ast
from pathlib import Path

import pytest

from insidegame.analytics.xt import xt_value
from insidegame.analytics.xt_grid import XT_FIT_MATCHES, XT_FIT_START_SEED, XT_GRID
from insidegame.analytics.xt_model import (
    XT_COLUMNS,
    XT_ROWS,
    TransitionCounts,
    cell_of,
    empty_counts,
    symmetrise,
    value_iteration,
)
from insidegame.core.exceptions import XtConvergenceError
from insidegame.core.geometry import Point
from insidegame.datasets.xt_fit import fit_grid, render_grid_module
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent

ANALYTICS = Path(__file__).resolve().parents[1] / "src" / "insidegame" / "analytics"
PURE_MODULES = ("xt_model.py", "xt.py", "xt_grid.py", "line_breaks.py", "threat.py", "threat_board.py",
                "threat_moments.py")
FORBIDDEN_PACKAGES = ("simulation", "tracking", "agents", "orchestration", "api", "live", "datasets")
TOLERANCE = 1e-9


def _event(kind: EventType, start: Point | None, end: Point | None = None,
           outcome: Outcome | None = None) -> MatchEvent:
    return MatchEvent("e1", "m", 1, 1, 10.0, kind, "home", "home-01", 1, start, 0, 0, end=end, outcome=outcome)


def _chain() -> TransitionCounts:
    """A: 10 actions, 5 completed moves to B. B: 10 actions, 4 shots worth 2.0 xG, 3 completed moves back to A."""
    a, b = (0, 0), (1, 0)
    return TransitionCounts(columns=3, rows=1, actions={a: 10, b: 10}, shots={b: 4}, shot_xg={b: 2.0},
                            moves={a: 10, b: 6}, transitions={(a, b): 5, (b, a): 3})


@pytest.mark.parametrize(("point", "cell"), [
    (Point(0.0, 0.0), (0, 0)), (Point(105.0, 68.0), (XT_COLUMNS - 1, XT_ROWS - 1)),
    (Point(-5.0, 80.0), (0, XT_ROWS - 1)), (Point(200.0, -3.0), (XT_COLUMNS - 1, 0)),
    (Point(52.5, 34.0), (6, 4)), (Point(8.74, 8.49), (0, 0)), (Point(8.75, 8.5), (1, 1)),
])
def test_cell_of_maps_edges_and_clamps_outside_points(point: Point, cell: tuple[int, int]) -> None:
    assert cell_of(point) == cell


def test_value_iteration_solves_a_chain_to_its_closed_form() -> None:
    grid = value_iteration(_chain())
    xt_b = 0.2 / (1 - 0.3 * 0.5)
    assert abs(grid[1][0] - xt_b) < 1e-5 and abs(grid[0][0] - 0.5 * xt_b) < 1e-5


def test_cells_without_actions_are_worth_zero() -> None:
    assert value_iteration(_chain())[2][0] == 0.0
    assert all(v == 0.0 for column in value_iteration(empty_counts()) for v in column)


def test_value_iteration_raises_when_it_cannot_converge() -> None:
    with pytest.raises(XtConvergenceError):
        value_iteration(_chain(), max_iterations=2)


def test_symmetrise_averages_mirrored_rows() -> None:
    grid = ((0.1, 0.2, 0.3, 0.6),)
    assert symmetrise(grid) == ((0.35, 0.25, 0.25, 0.35),)


def test_tackles_count_as_failed_moves_of_the_tackled_team_at_the_mirrored_cell() -> None:
    counts = empty_counts()
    counts.add_event(_event(EventType.TACKLE, Point(10.0, 5.0)))
    mirrored = cell_of(Point(95.0, 63.0))
    assert counts.actions == {mirrored: 1} and counts.moves == {mirrored: 1} and not counts.transitions


def test_moves_shots_and_ignored_events_are_counted_as_specified() -> None:
    counts = empty_counts()
    counts.add_event(_event(EventType.PASS, Point(10.0, 5.0), Point(60.0, 30.0), Outcome.SUCCESS))
    counts.add_event(_event(EventType.CARRY, Point(10.0, 5.0), Point(20.0, 5.0), Outcome.FAILURE))
    counts.add_event(_event(EventType.SHOT, Point(95.0, 34.0)))
    counts.add_event(_event(EventType.PRESSURE, Point(50.0, 34.0)))
    counts.add_event(_event(EventType.PASS, None, Point(60.0, 30.0), Outcome.SUCCESS))
    start = cell_of(Point(10.0, 5.0))
    assert counts.moves == {start: 2} and counts.transitions == {(start, cell_of(Point(60.0, 30.0))): 1}
    assert counts.shots == {cell_of(Point(95.0, 34.0)): 1} and sum(counts.actions.values()) == 3


def test_committed_grid_is_symmetric_and_peaks_near_goal() -> None:
    assert len(XT_GRID) == XT_COLUMNS and all(len(column) == XT_ROWS for column in XT_GRID)
    assert all(abs(c[r] - c[XT_ROWS - 1 - r]) < TOLERANCE for c in XT_GRID for r in range(XT_ROWS))
    assert xt_value(Point(100.0, 34.0)) == max(max(c) for c in XT_GRID)
    assert xt_value(Point(100.0, 34.0)) > xt_value(Point(52.5, 34.0)) > xt_value(Point(5.0, 34.0))


def test_committed_grid_regenerates_byte_for_byte() -> None:
    expected = render_grid_module(fit_grid(XT_FIT_MATCHES, XT_FIT_START_SEED), XT_FIT_MATCHES, XT_FIT_START_SEED)
    assert (ANALYTICS / "xt_grid.py").read_text(encoding="utf-8") == expected


@pytest.mark.parametrize("module", PURE_MODULES)
def test_pure_modules_never_import_higher_layers(module: str) -> None:
    tree = ast.parse((ANALYTICS / module).read_text(encoding="utf-8"))
    imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    imported += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in imported if m.split(".")[1:2] and m.split(".")[1] in FORBIDDEN_PACKAGES]
