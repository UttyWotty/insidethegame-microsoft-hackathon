"""Pure pitch-zone helpers: attacking channels across the width and thirds along the length.

Zones are expressed in a team's own attacking frame, where the right flank is high y as in tracking/formation.py.
opposite_flank maps a flank between the two teams' frames, because mirroring a point swaps left and right.
"""

from enum import StrEnum

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M

PITCH_THIRD_M: float = PITCH_LENGTH_M / 3
CHANNEL_WIDTH_M: float = PITCH_WIDTH_M / 3


class Channel(StrEnum):
    """A vertical strip of the pitch, seen from the team attacking toward x = PITCH_LENGTH_M."""

    LEFT = "left"
    CENTRE = "centre"
    RIGHT = "right"


class Third(StrEnum):
    """A horizontal third of the pitch, seen from the team attacking toward x = PITCH_LENGTH_M."""

    DEFENSIVE = "defensive"
    MIDDLE = "middle"
    FINAL = "final"


def channel_of(y: float) -> Channel:
    """Channel of a y coordinate in the acting team's frame: low y is the left, high y the right."""
    if y < CHANNEL_WIDTH_M:
        return Channel.LEFT
    return Channel.RIGHT if y >= 2 * CHANNEL_WIDTH_M else Channel.CENTRE


def third_of(x: float) -> Third:
    """Third of an x coordinate in the acting team's frame."""
    if x < PITCH_THIRD_M:
        return Third.DEFENSIVE
    return Third.FINAL if x >= 2 * PITCH_THIRD_M else Third.MIDDLE


def opposite_flank(channel: Channel) -> Channel:
    """The same strip seen from the other team's frame: left and right swap, the centre stays."""
    if channel is Channel.LEFT:
        return Channel.RIGHT
    return Channel.LEFT if channel is Channel.RIGHT else Channel.CENTRE
