"""Expected goals (xG) model estimating the scoring probability of a shot.

It is an independent logistic model on shot distance and goal angle with a pressure penalty.
It never reads the simulator's internal ground truth, mirroring how real analytics providers work.
"""

import math

from insidegame.core.geometry import Point, distance_to_goal, goal_angle

XG_INTERCEPT: float = -2.35
XG_DISTANCE_COEF: float = -0.10
XG_ANGLE_COEF: float = 1.5
PRESSURE_MULTIPLIER: float = 0.85
XG_DECIMALS: int = 3


def expected_goals(origin: Point, under_pressure: bool) -> float:
    """Return the probability in 0..1 that a shot from origin results in a goal."""
    logit = XG_INTERCEPT + XG_DISTANCE_COEF * distance_to_goal(origin) + XG_ANGLE_COEF * goal_angle(origin)
    probability = 1.0 / (1.0 + math.exp(-logit))
    if under_pressure:
        probability *= PRESSURE_MULTIPLIER
    return round(probability, XG_DECIMALS)
