"""Pure geometry for where a blocked shot stops: at the first defender in the ball's lane, or a short way out.

All points are in the shooter's attacking frame, where the ball travels from the shot origin toward GOAL_CENTER.
The blocker is the outfield opponent within BLOCK_LANE_M of that line and at least BLOCK_MIN_GAP_M in front of the
shooter, closest to them; the ball stops at their projection, else BLOCK_FALLBACK_M along the line, always at least
BLOCK_MIN_FLIGHT_M from the shooter and never closer than BLOCK_GOAL_CLEARANCE_M to the goal line.
"""

from collections.abc import Sequence

from insidegame.core.geometry import GOAL_CENTER, Point, distance

BLOCK_LANE_M: float = 1.5
"""Widest perpendicular distance from the shot line at which a defender counts as standing in the ball's lane."""
BLOCK_FALLBACK_M: float = 2.0
"""How far along the shot line the ball stops when no defender stands in its lane."""
BLOCK_MIN_GAP_M: float = 0.5
"""Candidates projecting closer than this in front of the shooter (the closing-down defender on top of them) are ignored."""
BLOCK_GOAL_CLEARANCE_M: float = 1.0
"""How far short of the goal line (along the attacking x axis) a blocked ball must stop at the latest."""
BLOCK_MIN_FLIGHT_M: float = 0.5
"""Shortest flight of a blocked ball, unless the goal clearance forbids it."""


def _along(origin: Point, unit: tuple[float, float], metres: float) -> Point:
    """The point metres from origin along the unit direction."""
    return Point(origin.x + unit[0] * metres, origin.y + unit[1] * metres)


def _nearest_blocker(origin: Point, unit: tuple[float, float], length: float, outfield: Sequence[Point]) -> float | None:
    """Distance along the shot line to the nearest candidate blocker in the lane, or None when there is none."""
    stops = []
    for player in outfield:
        dx, dy = player.x - origin.x, player.y - origin.y
        along = dx * unit[0] + dy * unit[1]
        across = abs(dx * unit[1] - dy * unit[0])
        if BLOCK_MIN_GAP_M <= along <= length and across <= BLOCK_LANE_M:
            stops.append(along)
    return min(stops) if stops else None


def _clearance_limit(origin: Point, unit: tuple[float, float]) -> float:
    """Longest flight along the line that keeps the ball BLOCK_GOAL_CLEARANCE_M short of the goal line (at least 0)."""
    room = GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M - origin.x
    if room <= 0.0:
        return 0.0
    return room / unit[0]


def block_point(origin: Point, outfield: Sequence[Point]) -> Point:
    """Where a blocked shot from origin stops, given the outfield opponents' positions.

    Candidates project onto the line from origin to GOAL_CENTER at least BLOCK_MIN_GAP_M in front of the shooter and
    no further than the goal, within BLOCK_LANE_M of the line; the nearest one wins, else the ball goes
    BLOCK_FALLBACK_M along the line. The flight is at least BLOCK_MIN_FLIGHT_M, but the stop is clamped to
    BLOCK_GOAL_CLEARANCE_M short of the goal line, which wins; a shot from within that clearance stops at its origin.
    """
    length = distance(origin, GOAL_CENTER)
    limit_x = GOAL_CENTER.x - BLOCK_GOAL_CLEARANCE_M
    if length == 0.0 or origin.x >= limit_x:
        return origin
    unit = ((GOAL_CENTER.x - origin.x) / length, (GOAL_CENTER.y - origin.y) / length)
    blocker = _nearest_blocker(origin, unit, length, outfield)
    wanted = max(BLOCK_FALLBACK_M if blocker is None else blocker, BLOCK_MIN_FLIGHT_M)
    limit = _clearance_limit(origin, unit)
    if wanted >= limit:
        return Point(limit_x, origin.y + unit[1] * limit)
    return _along(origin, unit, wanted)
