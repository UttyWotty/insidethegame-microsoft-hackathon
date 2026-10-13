"""Top-level match simulator that turns fixture metadata into a full event stream.

It plays two periods with random stoppage time, adapting each team's style to the game state.
The run is fully deterministic for a given MatchMetadata.seed.
"""

from insidegame.core.constants import PERIOD_SECONDS, PERIODS
from insidegame.core.geometry import PITCH_CENTER
from insidegame.domain.enums import EventType, Side
from insidegame.domain.match import MatchMetadata, MatchResult
from insidegame.simulation.open_play import apply_pressure, resolve_carry, resolve_pass
from insidegame.simulation.probabilities import ActionKind, choose_action, effective_style, venue_factor
from insidegame.simulation.set_pieces import kick_off, resolve_shot
from insidegame.simulation.state import SimState

STOPPAGE_MIN_S: float = 60.0
STOPPAGE_MAX_S: float = 300.0
FIRST_HALF_KICKER: Side = Side.HOME


def _step(state: SimState) -> None:
    attacking_style = effective_style(
        state.attacking_team.style, state.goal_difference(state.attacking), state.clock_s
    )
    defending_style = effective_style(
        state.defending_team.style, state.goal_difference(state.attacking.opponent), state.clock_s
    )
    apply_pressure(state, defending_style)
    action = choose_action(state.ball, state.carrier.attributes, attacking_style, state.under_pressure, state.rng,
                           venue_factor(state.attacking is Side.HOME))
    if action is ActionKind.SHOT:
        resolve_shot(state)
    elif action is ActionKind.CARRY:
        resolve_carry(state, defending_style)
    else:
        resolve_pass(state, attacking_style, defending_style)


def _play_period(state: SimState, period: int) -> None:
    period_start = (period - 1) * PERIOD_SECONDS
    period_end = period_start + PERIOD_SECONDS + state.rng.uniform(STOPPAGE_MIN_S, STOPPAGE_MAX_S)
    state.period = period
    state.clock_s = period_start
    state.emit(EventType.PERIOD_START, None, None, None)
    kicker = FIRST_HALF_KICKER if period == PERIODS[0] else FIRST_HALF_KICKER.opponent
    kick_off(state, kicker)
    while state.clock_s < period_end:
        _step(state)
    state.emit(EventType.PERIOD_END, None, None, PITCH_CENTER)


def simulate_match(metadata: MatchMetadata) -> MatchResult:
    """Simulate a full match and return its ordered event stream and final score."""
    state = SimState.new(metadata)
    for period in PERIODS:
        _play_period(state, period)
    return MatchResult(metadata, tuple(state.events), state.home_goals, state.away_goals)
