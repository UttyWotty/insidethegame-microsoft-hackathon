"""Pure game-state rule for synthetic tracking: how much deeper a team defends because of the score and clock.

A team leading from PROTECT_START_SECOND (70') defends PROTECT_DROP_M metres deeper out of possession, the
tracking counterpart of the simulator's existing "protect the lead" style rule, which shares the same start time.
The rule only moves player positions; it never changes events, scorelines, or calibration.
"""

from insidegame.simulation.probabilities import PROTECT_START_SECOND

PROTECT_DROP_M: float = 10.0
NO_DROP_M: float = 0.0


def protect_drop_m(goal_difference: int, match_second: float) -> float:
    """Out-of-possession depth offset in metres: PROTECT_DROP_M when leading at or after 70', else NO_DROP_M."""
    return PROTECT_DROP_M if goal_difference > 0 and match_second >= PROTECT_START_SECOND else NO_DROP_M
