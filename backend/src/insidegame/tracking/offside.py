"""Pure offside rule for tracked formation shapes: attackers off the ball stay level with or behind the offside line.

Formation slots push forward with the ball, so near goal a striker's slot would land on the goal line, an offside
position on every attack. The line is the second-last defender or the ball, whichever is further forward, and never
inside the attackers' own half; coordinates are in the attacking team's frame, attacking toward x = PITCH_LENGTH_M.
"""

from collections.abc import Sequence

from insidegame.core.constants import PITCH_LENGTH_M
from insidegame.core.geometry import Point

ONSIDE_MARGIN_M: float = 0.5
HALFWAY_X_M: float = PITCH_LENGTH_M / 2
SECOND_LAST: int = 1


def offside_line(defenders: Sequence[Point], ball: Point) -> float:
    """The offside line's x: the second-last defender, the ball, or halfway, whichever is furthest forward.

    With fewer than two defenders the second-last defender is taken as the goal line.
    """
    depths = sorted((d.x for d in defenders), reverse=True)
    second_last = depths[SECOND_LAST] if len(depths) > SECOND_LAST else PITCH_LENGTH_M
    return max(second_last, ball.x, HALFWAY_X_M)


def onside_positions(attackers: Sequence[Point], defenders: Sequence[Point], ball: Point,
                     margin_m: float = ONSIDE_MARGIN_M) -> list[Point]:
    """The attackers with every one beyond the offside line moved back to margin_m behind it (default 0.5 m).

    y is unchanged, and attackers already onside are returned as they are.
    """
    limit = offside_line(defenders, ball) - margin_m
    return [Point(min(a.x, limit), a.y) if a.x > limit else a for a in attackers]
