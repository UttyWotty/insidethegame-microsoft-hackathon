"""Pure geometry for where a saved shot stops: in front of the goal line, where the keeper meets the ball.

All points are in the shooter's attacking frame, where the goal line is x = PITCH_LENGTH_M and the ball travels from
the shot origin toward its placement on that line. The ball stops where the shot line reaches the keeper's distance
off the line (clamped to SAVE_MIN_DEPTH_M..SAVE_MAX_DEPTH_M, SAVE_DEFAULT_DEPTH_M without a keeper), at least
SAVE_MIN_FLIGHT_M from the shooter, but never closer than SAVE_MIN_DEPTH_M to the goal line, which wins.
"""

from insidegame.core.constants import GOAL_CENTER_Y_M, PITCH_LENGTH_M
from insidegame.core.geometry import Point, distance

SAVE_MIN_DEPTH_M: float = 0.3
"""Closest a saved ball may stop to the goal line (along the attacking x axis); a keeper on or behind the line saves here."""
SAVE_MAX_DEPTH_M: float = 3.0
"""Furthest off the line a save is shown; a keeper further out than this saves at this depth."""
SAVE_DEFAULT_DEPTH_M: float = 1.0
"""Save depth used when the keeper is absent from the shot frame."""
SAVE_MIN_FLIGHT_M: float = 0.5
"""Shortest flight of a saved ball, unless SAVE_MIN_DEPTH_M forbids it."""


def save_depth(keeper: Point | None) -> float:
    """The keeper's distance off the goal line, clamped to [SAVE_MIN_DEPTH_M, SAVE_MAX_DEPTH_M], or SAVE_DEFAULT_DEPTH_M."""
    if keeper is None:
        return SAVE_DEFAULT_DEPTH_M
    return min(max(PITCH_LENGTH_M - keeper.x, SAVE_MIN_DEPTH_M), SAVE_MAX_DEPTH_M)


def save_point(origin: Point, placement_y: float, keeper: Point | None) -> Point:
    """Where a saved shot from origin aimed at placement_y (metres from the goal centre) stops.

    The ball travels along the line from origin to (PITCH_LENGTH_M, GOAL_CENTER_Y_M + placement_y) and stops
    save_depth(keeper) short of the goal line. The flight is at least SAVE_MIN_FLIGHT_M, but the stop never passes
    x = PITCH_LENGTH_M - SAVE_MIN_DEPTH_M, which wins; a shot from at or inside that depth stops at its origin.
    """
    target = Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M + placement_y)
    limit_x = PITCH_LENGTH_M - SAVE_MIN_DEPTH_M
    length = distance(origin, target)
    if length == 0.0 or origin.x >= limit_x:
        return origin
    unit = ((target.x - origin.x) / length, (target.y - origin.y) / length)
    wanted = max((PITCH_LENGTH_M - save_depth(keeper) - origin.x) / unit[0], SAVE_MIN_FLIGHT_M)
    limit = (limit_x - origin.x) / unit[0]
    if wanted >= limit:
        return Point(limit_x, origin.y + unit[1] * limit)
    return Point(origin.x + unit[0] * wanted, origin.y + unit[1] * wanted)
