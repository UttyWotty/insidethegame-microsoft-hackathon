"""Pure probability models that drive simulated on-ball decisions and outcomes.

Each function maps pitch geometry, player attributes, and team style to a probability in 0..1.
The only randomness is in choose_action, which takes an injected random.Random for determinism.
"""

import math
import random
from enum import StrEnum

from insidegame.core.constants import PERIOD_SECONDS, PITCH_LENGTH_M
from insidegame.core.geometry import Point, distance_to_goal, goal_angle
from insidegame.domain.teams import PlayerAttributes, TeamStyle

MATCH_SECONDS: int = 2 * PERIOD_SECONDS

MAX_SHOT_DISTANCE_M: float = 35.0
SHOT_DECAY_M: float = 23.0
SHOT_BASE_SCALE: float = 0.18
SHOT_RISK_FLOOR: float = 0.6
SHOT_RISK_WEIGHT: float = 0.8
SHOT_OPENNESS_POWER: float = 2.0

CARRY_BASE: float = 0.22
CARRY_PACE_WEIGHT: float = 0.18
CARRY_PRESSURE_PENALTY: float = 0.10

PASS_BASE: float = 1.025
PASS_LENGTH_PENALTY_PER_M: float = 0.0035
PASS_PRESSURE_PENALTY: float = 0.10
PASS_PRESSING_PENALTY: float = 0.06
PASS_SKILL_WEIGHT: float = 0.10
PASS_FINAL_THIRD_PENALTY: float = 0.15
PASS_SKILL_PIVOT: float = 0.5

TACKLE_BASE: float = 0.04
TACKLE_SKILL_WEIGHT: float = 0.12
TACKLE_PRESSING_WEIGHT: float = 0.08
TACKLE_PACE_WEIGHT: float = 0.08

PRESSURE_BASE: float = 0.12
PRESSURE_PRESSING_WEIGHT: float = 0.30

XG_INTERCEPT: float = -1.90
XG_DISTANCE_COEF: float = -0.11
XG_ANGLE_COEF: float = 1.6
FINISHING_FLOOR: float = 0.7
FINISHING_WEIGHT: float = 0.6

FATIGUE_MAX_PENALTY: float = 0.05

NEUTRAL_VENUE: float = 1.0
HOME_SHOT_FACTOR: float = 1.32
AWAY_SHOT_FACTOR: float = 0.80

CHASE_START_SECOND: float = 60 * 60
PROTECT_START_SECOND: float = 70 * 60
CHASE_BOOST: float = 0.20
PROTECT_DAMPING: float = 0.15

PROBABILITY_MIN: float = 0.01
PROBABILITY_MAX: float = 0.99


class ActionKind(StrEnum):
    """Decision the ball carrier takes on a touch."""

    PASS = "pass"
    CARRY = "carry"
    SHOT = "shot"


def _bounded(p: float) -> float:
    return min(max(p, PROBABILITY_MIN), PROBABILITY_MAX)


def _unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def effective_style(style: TeamStyle, goal_difference: int, match_second: float) -> TeamStyle:
    """Adapt a team's style to the game state: chase when trailing late, protect when leading late."""
    if goal_difference < 0 and match_second >= CHASE_START_SECOND:
        shift = CHASE_BOOST
    elif goal_difference > 0 and match_second >= PROTECT_START_SECOND:
        shift = -PROTECT_DAMPING
    else:
        return style
    return TeamStyle(
        label=style.label,
        directness=_unit(style.directness + shift),
        pressing=_unit(style.pressing + shift),
        risk=_unit(style.risk + shift),
        weak_flank=style.weak_flank,
    )


def fatigue_factor(match_second: float) -> float:
    """Return a multiplier below 1.0 that grows as the match wears on."""
    return 1.0 - FATIGUE_MAX_PENALTY * _unit(match_second / MATCH_SECONDS)


def venue_factor(is_home: bool) -> float:
    """Shot-volume multiplier for home advantage: home sides create more chances, away sides fewer."""
    return HOME_SHOT_FACTOR if is_home else AWAY_SHOT_FACTOR


def shot_probability(ball: Point, attrs: PlayerAttributes, style: TeamStyle, venue: float = NEUTRAL_VENUE) -> float:
    """Probability the carrier shoots from the current location; venue defaults to NEUTRAL_VENUE (1.0)."""
    d = distance_to_goal(ball)
    if d > MAX_SHOT_DISTANCE_M:
        return 0.0
    base = SHOT_BASE_SCALE * math.exp(-d / SHOT_DECAY_M) * venue * openness(ball)
    return _bounded(base * (SHOT_RISK_FLOOR + SHOT_RISK_WEIGHT * style.risk) * (0.5 + attrs.finishing))


def openness(ball: Point) -> float:
    """How square-on the shooter is to goal: 1.0 on the goal's centre line at any distance, falling toward 0 at the
    byline, so players rarely shoot from tight angles while long central shots stay possible."""
    d = distance_to_goal(ball)
    return ((PITCH_LENGTH_M - ball.x) / d) ** SHOT_OPENNESS_POWER if d > 0 else 1.0


def carry_probability(attrs: PlayerAttributes, under_pressure: bool) -> float:
    """Probability the carrier dribbles forward rather than passes."""
    penalty = CARRY_PRESSURE_PENALTY if under_pressure else 0.0
    return _bounded(CARRY_BASE + CARRY_PACE_WEIGHT * attrs.pace - penalty)


def choose_action(
    ball: Point, attrs: PlayerAttributes, style: TeamStyle, under_pressure: bool, rng: random.Random,
    venue: float = NEUTRAL_VENUE,
) -> ActionKind:
    """Sample the carrier's next action; venue (default NEUTRAL_VENUE) scales the chance of shooting."""
    p_shot = shot_probability(ball, attrs, style, venue)
    draw = rng.random()
    if draw < p_shot:
        return ActionKind.SHOT
    p_carry = carry_probability(attrs, under_pressure) * (1.0 - p_shot)
    return ActionKind.CARRY if draw < p_shot + p_carry else ActionKind.PASS


def pass_success_probability(
    length_m: float, target_x: float, attrs: PlayerAttributes, under_pressure: bool,
    opponent_pressing: float, match_second: float,
) -> float:
    """Probability a pass of the given length reaches its target."""
    p = PASS_BASE - PASS_LENGTH_PENALTY_PER_M * length_m
    p += PASS_SKILL_WEIGHT * (attrs.passing - PASS_SKILL_PIVOT)
    p -= PASS_PRESSURE_PENALTY if under_pressure else 0.0
    p -= PASS_PRESSING_PENALTY * opponent_pressing
    p -= PASS_FINAL_THIRD_PENALTY * _unit(target_x / PITCH_LENGTH_M)
    return _bounded(p * fatigue_factor(match_second))


def tackle_probability(carrier: PlayerAttributes, defender: PlayerAttributes, opponent_pressing: float) -> float:
    """Probability a carry is ended by a defensive challenge."""
    p = TACKLE_BASE + TACKLE_SKILL_WEIGHT * defender.tackling
    p += TACKLE_PRESSING_WEIGHT * opponent_pressing - TACKLE_PACE_WEIGHT * carrier.pace
    return _bounded(p)


def pressure_probability(ball_x: float, opponent_pressing: float) -> float:
    """Probability the defending team closes down the carrier; higher presses engage further up."""
    own_half_factor = 1.0 - _unit(ball_x / PITCH_LENGTH_M)
    return _bounded(PRESSURE_BASE + PRESSURE_PRESSING_WEIGHT * opponent_pressing * own_half_factor)


def scoring_probability(ball: Point, finishing: float) -> float:
    """Ground-truth probability that a shot from this location by this finisher scores."""
    logit = XG_INTERCEPT + XG_DISTANCE_COEF * distance_to_goal(ball) + XG_ANGLE_COEF * goal_angle(ball)
    base = 1.0 / (1.0 + math.exp(-logit))
    return _bounded(base * (FINISHING_FLOOR + FINISHING_WEIGHT * finishing))
