"""Pure expected threat (xT) lookup against the committed grid fitted to the synthetic league.

A point in the acting team's attacking frame maps to its grid cell, and the cell's value is the probability that
possession there leads to a goal in the next few actions. Points outside the pitch are clamped to its edge.
"""

from insidegame.analytics.xt_grid import XT_GRID
from insidegame.analytics.xt_model import cell_of
from insidegame.core.geometry import Point


def xt_value(point: Point) -> float:
    """Return the xT of a point in the acting team's attacking frame."""
    column, row = cell_of(point)
    return XT_GRID[column][row]
