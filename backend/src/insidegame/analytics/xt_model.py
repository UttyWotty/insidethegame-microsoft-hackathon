"""Pure expected threat (xT) model: grid cells, transition counting, value iteration, and mirror symmetrisation.

Events are counted in the acting team's attacking frame on a XT_COLUMNS x XT_ROWS grid, and value iteration solves
xT(c) = s(c) * g(c) + m(c) * sum_d T(c, d) * xT(d), where shots are valued by our own xG model.
Symmetrising across the pitch's long axis removes any one-sided bias of the simulated clubs from the fitted grid.
"""

from dataclasses import dataclass, field

from insidegame.analytics.xg import expected_goals
from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.exceptions import XtConvergenceError
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent

XT_COLUMNS: int = 12
XT_ROWS: int = 8
XT_TOLERANCE: float = 1e-6
XT_MAX_ITERATIONS: int = 200
MOVE_TYPES: frozenset[EventType] = frozenset({EventType.PASS, EventType.CARRY})

XtGrid = tuple[tuple[float, ...], ...]
Cell = tuple[int, int]


def _index(value: float, extent: float, count: int) -> int:
    """Bucket index of a coordinate clamped to 0..extent; the far edge falls in the last bucket."""
    clamped = min(max(value, 0.0), extent)
    return min(int(clamped / (extent / count)), count - 1)


def cell_of(point: Point, columns: int = XT_COLUMNS, rows: int = XT_ROWS) -> Cell:
    """Return the (column, row) cell holding a point, clamping points outside the pitch to its edge.

    Defaults: columns is XT_COLUMNS and rows is XT_ROWS, the grid shape of the committed XT_GRID.
    """
    return _index(point.x, PITCH_LENGTH_M, columns), _index(point.y, PITCH_WIDTH_M, rows)


@dataclass
class TransitionCounts:
    """Per-cell action, shot, and move counts plus completed move transitions, in the acting team's frame."""

    columns: int
    rows: int
    actions: dict[Cell, int] = field(default_factory=dict)
    shots: dict[Cell, int] = field(default_factory=dict)
    shot_xg: dict[Cell, float] = field(default_factory=dict)
    moves: dict[Cell, int] = field(default_factory=dict)
    transitions: dict[tuple[Cell, Cell], int] = field(default_factory=dict)

    def _cell(self, point: Point) -> Cell:
        return cell_of(point, self.columns, self.rows)

    def _act(self, cell: Cell) -> None:
        self.actions[cell] = self.actions.get(cell, 0) + 1

    def _move(self, cell: Cell) -> None:
        self._act(cell)
        self.moves[cell] = self.moves.get(cell, 0) + 1

    def add_event(self, event: MatchEvent) -> None:
        """Count one event: shots, passes and carries (moves), and tackles as failed moves of the tackled team."""
        if event.start is None:
            return
        kind = event.event_type
        if kind is EventType.SHOT:
            cell = self._cell(event.start)
            self._act(cell)
            self.shots[cell] = self.shots.get(cell, 0) + 1
            self.shot_xg[cell] = self.shot_xg.get(cell, 0.0) + expected_goals(event.start, event.under_pressure)
        elif kind in MOVE_TYPES and event.end is not None:
            cell = self._cell(event.start)
            self._move(cell)
            if event.outcome is Outcome.SUCCESS:
                key = (cell, self._cell(event.end))
                self.transitions[key] = self.transitions.get(key, 0) + 1
        elif kind is EventType.TACKLE:
            self._move(self._cell(mirror(event.start)))


def empty_counts(columns: int = XT_COLUMNS, rows: int = XT_ROWS) -> TransitionCounts:
    """Return empty counts for a grid; defaults are XT_COLUMNS by XT_ROWS."""
    return TransitionCounts(columns=columns, rows=rows)


def _cells(columns: int, rows: int) -> list[Cell]:
    return [(c, r) for c in range(columns) for r in range(rows)]


def _shot_values(counts: TransitionCounts) -> dict[Cell, float]:
    """s(c) * g(c): the immediate scoring value of acting in a cell, 0 for cells without actions or shots."""
    values: dict[Cell, float] = {}
    for cell, actions in counts.actions.items():
        shots = counts.shots.get(cell, 0)
        values[cell] = (shots / actions) * (counts.shot_xg.get(cell, 0.0) / shots) if shots else 0.0
    return values


def _move_weights(counts: TransitionCounts) -> dict[Cell, list[tuple[Cell, float]]]:
    """m(c) * T(c, d) for every completed transition, as (destination, weight) lists per start cell."""
    weights: dict[Cell, list[tuple[Cell, float]]] = {}
    for (start, end), count in sorted(counts.transitions.items()):
        weights.setdefault(start, []).append((end, count / counts.actions[start]))
    return weights


def value_iteration(counts: TransitionCounts, tolerance: float = XT_TOLERANCE,
                    max_iterations: int = XT_MAX_ITERATIONS) -> XtGrid:
    """Solve the xT grid by repeated sweeps until no cell changes by more than tolerance.

    Defaults: tolerance is XT_TOLERANCE and max_iterations is XT_MAX_ITERATIONS.
    Cells without actions are worth 0. Raises XtConvergenceError when max_iterations sweeps do not converge.
    """
    cells = _cells(counts.columns, counts.rows)
    shot_value, weights = _shot_values(counts), _move_weights(counts)
    xt = dict.fromkeys(cells, 0.0)
    for _ in range(max_iterations):
        new = {cell: shot_value.get(cell, 0.0) + sum(w * xt[end] for end, w in weights.get(cell, ()))
               for cell in cells}
        delta = max(abs(new[cell] - xt[cell]) for cell in cells)
        xt = new
        if delta < tolerance:
            return tuple(tuple(xt[(c, r)] for r in range(counts.rows)) for c in range(counts.columns))
    raise XtConvergenceError(f"xT value iteration did not converge within {max_iterations} sweeps")


def symmetrise(grid: XtGrid) -> XtGrid:
    """Average each row with its mirror row (row r with row rows-1-r), so both flanks carry equal threat."""
    return tuple(tuple((column[r] + column[len(column) - 1 - r]) / 2 for r in range(len(column))) for column in grid)
