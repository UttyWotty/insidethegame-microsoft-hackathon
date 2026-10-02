"""Resolvers for shots and the restarts that follow them, plus kick-offs.

A shot can be blocked, scored, saved, or miss the target, each leading to a different restart.
Kick-offs start each period and follow every goal.
"""

from insidegame.core.constants import GOAL_CENTER_Y_M, GOAL_WIDTH_M, PITCH_LENGTH_M
from insidegame.core.geometry import GOAL_CENTER, PITCH_CENTER, Point, distance_to_goal, mirror
from insidegame.domain.enums import EventType, Outcome, Position, ShotResult, Side
from insidegame.simulation.probabilities import scoring_probability
from insidegame.simulation.selection import pick_defender
from insidegame.simulation.state import SimState

GOAL_CELEBRATION_S: float = 45.0
GOAL_KICK_DELAY_S: float = 20.0
SAVE_HOLD_S: float = 6.0
BLOCK_RECOVERY_S: float = 2.0

BLOCK_BASE: float = 0.15
BLOCK_PRESSURE_BONUS: float = 0.10
ON_TARGET_GIVEN_NO_GOAL: float = 0.40

SHOT_SPEED_BASE_KMH: float = 70.0
SHOT_SPEED_FINISHING_KMH: float = 30.0
SHOT_SPEED_PER_M_KMH: float = 0.6
SHOT_SPEED_SD_KMH: float = 8.0
SHOT_SPEED_MIN_KMH: float = 40.0
SHOT_SPEED_MAX_KMH: float = 135.0

GOAL_KICK_SPOT: Point = Point(6.0, GOAL_CENTER_Y_M)
KEEPER_RELEASE_SPOT: Point = Point(10.0, GOAL_CENTER_Y_M)
KEEPER_SAVE_SPOT: Point = Point(1.5, GOAL_CENTER_Y_M)
MISS_WIDE_OFFSET_M: float = GOAL_WIDTH_M / 2 + 2.0


def kick_off(state: SimState, side: Side) -> None:
    """Restart from the centre spot with side in possession."""
    forwards = state.metadata.team(side).players_in(Position.FORWARD)
    state.attacking = side
    state.carrier = state.rng.choice(forwards)
    state.ball = PITCH_CENTER
    state.under_pressure = False
    state.possession_id += 1
    state.emit(EventType.KICK_OFF, side, state.carrier, PITCH_CENTER)


def _shot_speed(state: SimState) -> float:
    finishing = state.carrier.attributes.finishing
    mean = SHOT_SPEED_BASE_KMH + SHOT_SPEED_FINISHING_KMH * finishing + SHOT_SPEED_PER_M_KMH * distance_to_goal(state.ball)
    return min(max(state.rng.gauss(mean, SHOT_SPEED_SD_KMH), SHOT_SPEED_MIN_KMH), SHOT_SPEED_MAX_KMH)


def _emit_shot(state: SimState, result: ShotResult, end: Point | None, speed: float) -> None:
    outcome = Outcome.SUCCESS if result is ShotResult.GOAL else Outcome.FAILURE
    state.emit(EventType.SHOT, state.attacking, state.carrier, state.ball, end=end, outcome=outcome,
               under_pressure=state.under_pressure, ball_speed_kmh=speed, shot_result=result)


def resolve_shot(state: SimState) -> None:
    """Simulate a shot and the restart that follows it."""
    rng, shooter_side, origin = state.rng, state.attacking, state.ball
    defending_side = shooter_side.opponent
    keeper = state.defending_team.goalkeeper()
    speed = _shot_speed(state)
    p_block = BLOCK_BASE + (BLOCK_PRESSURE_BONUS if state.under_pressure else 0.0)
    if rng.random() < p_block:
        _emit_shot(state, ShotResult.BLOCKED, None, speed)
        blocker = pick_defender(state.defending_team, origin.x, rng)
        state.advance(BLOCK_RECOVERY_S)
        state.give_possession(defending_side, blocker, mirror(origin))
        return
    if rng.random() < scoring_probability(origin, state.carrier.attributes.finishing):
        _emit_shot(state, ShotResult.GOAL, GOAL_CENTER, speed)
        state.add_goal(shooter_side)
        state.emit(EventType.GOAL, shooter_side, state.carrier, origin)
        state.advance(GOAL_CELEBRATION_S)
        kick_off(state, defending_side)
        return
    if rng.random() < ON_TARGET_GIVEN_NO_GOAL:
        _emit_shot(state, ShotResult.SAVED, GOAL_CENTER, speed)
        state.emit(EventType.SAVE, defending_side, keeper, KEEPER_SAVE_SPOT, outcome=Outcome.SUCCESS,
                   opponent_id=state.carrier.player_id)
        state.advance(SAVE_HOLD_S)
        state.give_possession(defending_side, keeper, KEEPER_RELEASE_SPOT)
        return
    wide_y = GOAL_CENTER_Y_M + rng.choice((-1.0, 1.0)) * MISS_WIDE_OFFSET_M
    _emit_shot(state, ShotResult.OFF_TARGET, Point(PITCH_LENGTH_M, wide_y), speed)
    state.advance(GOAL_KICK_DELAY_S)
    state.give_possession(defending_side, keeper, GOAL_KICK_SPOT)
