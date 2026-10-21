"""Pure helpers for the simulator's weak-flank tendency: every club has a defensive flank opponents attack.

The defending club's weak flank is configured in its own frame, so the attacker sees it as the opposite flank.
Helpers give the lateral pull applied to attacking passes and tell whether a point lies in the exploited zone.
"""

from insidegame.core.geometry import Point
from insidegame.core.zones import Channel, Third, channel_of, opposite_flank, third_of
from insidegame.domain.teams import TeamStyle

WEAK_FLANK_LATERAL_SHIFT_M: float = 5.0
EXPLOIT_START_X_M: float = 45.0
WEAK_FLANK_PASS_BONUS: float = 0.04
WEAK_FLANK_TACKLE_REDUCTION: float = 0.02
WEAK_FLANK_TACKLE_START_X_M: float = 50.0
TOWARD_HIGH_Y: float = 1.0
TOWARD_LOW_Y: float = -1.0
NO_SHIFT_M: float = 0.0


def exploited_channel(defending: TeamStyle) -> Channel:
    """The attacker-frame channel that faces the defending club's weak flank."""
    return opposite_flank(defending.weak_flank)


def lateral_shift(ball: Point, defending: TeamStyle) -> float:
    """Signed metres added to the mean lateral pass offset; 0.0 before EXPLOIT_START_X_M or with no weak flank."""
    channel = exploited_channel(defending)
    if ball.x < EXPLOIT_START_X_M or channel is Channel.CENTRE:
        return NO_SHIFT_M
    direction = TOWARD_HIGH_Y if channel is Channel.RIGHT else TOWARD_LOW_Y
    return direction * WEAK_FLANK_LATERAL_SHIFT_M


def in_exploited_final_third(target: Point, defending: TeamStyle) -> bool:
    """True when a pass target lies in the final third, inside the channel facing the weak flank."""
    channel = exploited_channel(defending)
    return channel is not Channel.CENTRE and third_of(target.x) is Third.FINAL and channel_of(target.y) is channel


def in_exploited_flank(ball: Point, defending: TeamStyle) -> bool:
    """True when a carry starts at or beyond WEAK_FLANK_TACKLE_START_X_M in the channel facing the weak flank."""
    channel = exploited_channel(defending)
    return (channel is not Channel.CENTRE and ball.x >= WEAK_FLANK_TACKLE_START_X_M
            and channel_of(ball.y) is channel)
