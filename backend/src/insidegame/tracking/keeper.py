"""Pure goalkeeper positioning for synthetic tracking, in the keeper's own frame with its goal at x = 0.

Far from goal the keeper steps off the line in proportion to the ball's depth and follows it a quarter of the way across.
Within KEEPER_NARROW_RANGE_M of the goal centre the keeper narrows the angle, standing on the goal-to-ball line.
That keeps the keeper strictly between a close shooter and the goal, as a real keeper would be.
"""

from insidegame.core.constants import GOAL_CENTER_Y_M
from insidegame.core.geometry import Point, distance

KEEPER_BASE_X: float = 4.0
KEEPER_STEP: float = 0.08
KEEPER_MAX_STEP_M: float = 12.0
KEEPER_FOLLOW_Y: float = 0.25
KEEPER_NARROW_RANGE_M: float = 20.0
KEEPER_NARROW_FRACTION: float = 0.3
OWN_GOAL_CENTER: Point = Point(0.0, GOAL_CENTER_Y_M)


def keeper_spot(ball: Point) -> Point:
    """Return the keeper's target for a ball in the keeper's own frame (own goal at x = 0).

    Within KEEPER_NARROW_RANGE_M (inclusive) of the own goal centre the keeper stands KEEPER_NARROW_FRACTION of the
    way from the goal centre to the ball; otherwise it steps out with the ball's depth and follows it laterally.
    """
    if distance(ball, OWN_GOAL_CENTER) <= KEEPER_NARROW_RANGE_M:
        return Point(OWN_GOAL_CENTER.x + (ball.x - OWN_GOAL_CENTER.x) * KEEPER_NARROW_FRACTION,
                     OWN_GOAL_CENTER.y + (ball.y - OWN_GOAL_CENTER.y) * KEEPER_NARROW_FRACTION)
    return Point(KEEPER_BASE_X + min(ball.x * KEEPER_STEP, KEEPER_MAX_STEP_M),
                 GOAL_CENTER_Y_M + (ball.y - GOAL_CENTER_Y_M) * KEEPER_FOLLOW_Y)
