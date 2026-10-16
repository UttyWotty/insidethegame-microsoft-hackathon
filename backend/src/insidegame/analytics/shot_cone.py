"""Pure shot-cone geometry: the triangle from a shot's origin to both goal posts, and who stands inside it.

All points are in the shooter's attacking frame, where the attacked goal line is x = PITCH_LENGTH_M.
Occupancy counts outfield opponents inside the triangle (edges and vertices included) and flags the goalkeeper.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from insidegame.core.constants import GOAL_CENTER_Y_M, GOAL_WIDTH_M, PITCH_LENGTH_M
from insidegame.core.geometry import Point

HALF_GOAL_M: float = GOAL_WIDTH_M / 2


@dataclass(frozen=True)
class ConeOccupancy:
    """How many outfield opponents stand in the shot cone, and whether the goalkeeper does."""

    defenders: int
    keeper: bool


def cone_points(origin: Point) -> tuple[Point, Point, Point]:
    """The shot cone as origin, then the near-y post and the far-y post on the attacked goal line."""
    return (origin, Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M - HALF_GOAL_M),
            Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M + HALF_GOAL_M))


def _cross(p: Point, a: Point, b: Point) -> float:
    """Signed area test: which side of the line a -> b the point p lies on (zero on the line)."""
    return (p.x - b.x) * (a.y - b.y) - (a.x - b.x) * (p.y - b.y)


def in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    """Whether point lies inside the triangle abc; points on an edge or a vertex count as inside."""
    d1, d2, d3 = _cross(point, a, b), _cross(point, b, c), _cross(point, c, a)
    has_negative = d1 < 0 or d2 < 0 or d3 < 0
    has_positive = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_negative and has_positive)


def cone_occupancy(origin: Point, outfield: Sequence[Point], keeper: Point | None) -> ConeOccupancy:
    """Count outfield opponents in the cone from origin and flag the keeper; None for keeper means not tracked."""
    a, b, c = cone_points(origin)
    defenders = sum(1 for point in outfield if in_triangle(point, a, b, c))
    return ConeOccupancy(defenders, keeper is not None and in_triangle(keeper, a, b, c))
