"""Resolvers for open-play actions: pressure, passes, and carries.

Each resolver samples an outcome, emits the corresponding events, and updates SimState.
Turnovers hand possession to the defending side with coordinates mirrored into its frame.
"""

from insidegame.core.geometry import Point, clamp_to_pitch, distance, mirror
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.teams import TeamStyle
from insidegame.simulation.probabilities import (
    pass_success_probability,
    pressure_probability,
    tackle_probability,
)
from insidegame.simulation.selection import pick_defender, pick_receiver
from insidegame.simulation.state import SimState

MIN_ACTION_S: float = 0.5
PASS_TIME_BASE_S: float = 1.0
PASS_METRES_PER_SECOND: float = 14.0
PASS_TIME_JITTER_MEAN_S: float = 1.5
PASS_TIME_JITTER_SD_S: float = 0.7
PASS_FORWARD_BASE_M: float = 3.0
PASS_FORWARD_DIRECTNESS_M: float = 15.0
PASS_FORWARD_SD_M: float = 9.0
PASS_LATERAL_SD_M: float = 13.0
MIN_PASS_X_M: float = 1.0
MAX_PASS_X_M: float = 103.0

BALL_SPEED_BASE_KMH: float = 25.0
BALL_SPEED_PER_M_KMH: float = 1.4
BALL_SPEED_SD_KMH: float = 5.0
BALL_SPEED_MIN_KMH: float = 10.0
BALL_SPEED_MAX_KMH: float = 110.0

CARRY_FORWARD_BASE_M: float = 5.0
CARRY_FORWARD_PACE_M: float = 7.0
CARRY_FORWARD_SD_M: float = 3.0
CARRY_MIN_M: float = 2.0
CARRY_MAX_M: float = 20.0
CARRY_LATERAL_SD_M: float = 4.0
CARRY_SPEED_BASE_MS: float = 4.0
CARRY_SPEED_PACE_MS: float = 3.0
CARRY_EXTRA_S: float = 1.0
CARRY_MAX_X_M: float = 104.0

FOUL_PROBABILITY: float = 0.15
FREE_KICK_DELAY_S: float = 15.0
TURNOVER_DELAY_S: float = 1.0
CONTEST_FRACTION: float = 0.5


def apply_pressure(state: SimState, defending_style: TeamStyle) -> None:
    """Possibly have a defender close down the carrier, setting state.under_pressure."""
    rng = state.rng
    state.under_pressure = rng.random() < pressure_probability(state.ball.x, defending_style.pressing)
    if not state.under_pressure:
        return
    presser = pick_defender(state.defending_team, state.ball.x, rng)
    state.emit(EventType.PRESSURE, state.attacking.opponent, presser, mirror(state.ball),
               opponent_id=state.carrier.player_id)


def _pass_target(state: SimState, style: TeamStyle) -> Point:
    rng = state.rng
    forward = rng.gauss(PASS_FORWARD_BASE_M + PASS_FORWARD_DIRECTNESS_M * style.directness, PASS_FORWARD_SD_M)
    lateral = rng.gauss(0.0, PASS_LATERAL_SD_M)
    target = clamp_to_pitch(Point(state.ball.x + forward, state.ball.y + lateral))
    return Point(min(max(target.x, MIN_PASS_X_M), MAX_PASS_X_M), target.y)


def _ball_speed(state: SimState, length_m: float) -> float:
    speed = state.rng.gauss(BALL_SPEED_BASE_KMH + BALL_SPEED_PER_M_KMH * length_m, BALL_SPEED_SD_KMH)
    return min(max(speed, BALL_SPEED_MIN_KMH), BALL_SPEED_MAX_KMH)


def resolve_pass(state: SimState, style: TeamStyle, defending_style: TeamStyle) -> None:
    """Simulate a pass, completing it or turning possession over via interception."""
    rng, origin, passer = state.rng, state.ball, state.carrier
    target = _pass_target(state, style)
    length = distance(origin, target)
    receiver = pick_receiver(state.attacking_team, passer, target.x, rng)
    p_success = pass_success_probability(length, target.x, passer.attributes, state.under_pressure,
                                         defending_style.pressing, state.clock_s)
    success = rng.random() < p_success
    state.emit(EventType.PASS, state.attacking, passer, origin, end=target,
               outcome=Outcome.SUCCESS if success else Outcome.FAILURE, receiver_id=receiver.player_id,
               under_pressure=state.under_pressure, length_m=length, ball_speed_kmh=_ball_speed(state, length))
    duration = PASS_TIME_BASE_S + length / PASS_METRES_PER_SECOND
    state.advance(max(MIN_ACTION_S, duration + rng.gauss(PASS_TIME_JITTER_MEAN_S, PASS_TIME_JITTER_SD_S)))
    if success:
        state.carrier, state.ball, state.under_pressure = receiver, target, False
        return
    interceptor = pick_defender(state.defending_team, target.x, rng)
    state.emit(EventType.INTERCEPTION, state.attacking.opponent, interceptor, mirror(target),
               outcome=Outcome.SUCCESS, opponent_id=receiver.player_id)
    state.advance(TURNOVER_DELAY_S)
    state.give_possession(state.attacking.opponent, interceptor, mirror(target))


def _carry_end(state: SimState) -> Point:
    rng, pace = state.rng, state.carrier.attributes.pace
    forward = rng.gauss(CARRY_FORWARD_BASE_M + CARRY_FORWARD_PACE_M * pace, CARRY_FORWARD_SD_M)
    forward = min(max(forward, CARRY_MIN_M), CARRY_MAX_M)
    end = clamp_to_pitch(Point(state.ball.x + forward, state.ball.y + rng.gauss(0.0, CARRY_LATERAL_SD_M)))
    return Point(min(end.x, CARRY_MAX_X_M), end.y)


def _contest_point(start: Point, end: Point) -> Point:
    return Point(start.x + (end.x - start.x) * CONTEST_FRACTION, start.y + (end.y - start.y) * CONTEST_FRACTION)


def resolve_carry(state: SimState, defending_style: TeamStyle) -> None:
    """Simulate a dribble that may be tackled, fouled, or completed."""
    rng, origin, carrier = state.rng, state.ball, state.carrier
    end = _carry_end(state)
    defender = pick_defender(state.defending_team, origin.x, rng)
    p_tackle = tackle_probability(carrier.attributes, defender.attributes, defending_style.pressing)
    if rng.random() >= p_tackle:
        length = distance(origin, end)
        state.emit(EventType.CARRY, state.attacking, carrier, origin, end=end, outcome=Outcome.SUCCESS,
                   under_pressure=state.under_pressure, length_m=length)
        state.advance(length / (CARRY_SPEED_BASE_MS + CARRY_SPEED_PACE_MS * carrier.attributes.pace) + CARRY_EXTRA_S)
        state.ball, state.under_pressure = end, False
        return
    contest = _contest_point(origin, end)
    defending_side = state.attacking.opponent
    if rng.random() < FOUL_PROBABILITY:
        state.emit(EventType.FOUL, defending_side, defender, mirror(contest), opponent_id=carrier.player_id)
        state.advance(FREE_KICK_DELAY_S)
        state.ball, state.under_pressure = contest, False
        return
    state.emit(EventType.TACKLE, defending_side, defender, mirror(contest), outcome=Outcome.SUCCESS,
               opponent_id=carrier.player_id)
    state.advance(TURNOVER_DELAY_S)
    state.give_possession(defending_side, defender, mirror(contest))
