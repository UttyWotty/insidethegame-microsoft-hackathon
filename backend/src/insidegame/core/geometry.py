"""Pure geometry helpers for positions on the pitch.

Points are expressed in metres relative to the acting team, attacking toward x = PITCH_LENGTH_M.
Helpers cover distances, goal angles, clamping, and mirroring between team perspectives.
"""

import math
from dataclasses import dataclass

from insidegame.core.constants import GOAL_CENTER_Y_M, GOAL_WIDTH_M, PITCH_LENGTH_M, PITCH_WIDTH_M

COORDINATE_DECIMALS: int = 2


@dataclass(frozen=True)
class Point:
    """A location on the pitch in metres."""

    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-friendly representation rounded to centimetres."""
        return {"x": round(self.x, COORDINATE_DECIMALS), "y": round(self.y, COORDINATE_DECIMALS)}


PITCH_CENTER: Point = Point(PITCH_LENGTH_M / 2, PITCH_WIDTH_M / 2)
GOAL_CENTER: Point = Point(PITCH_LENGTH_M, GOAL_CENTER_Y_M)


def distance(a: Point, b: Point) -> float:
    """Return the Euclidean distance between two points in metres."""
    return math.hypot(b.x - a.x, b.y - a.y)


def distance_to_goal(p: Point) -> float:
    """Return the distance from a point to the centre of the attacked goal."""
    return distance(p, GOAL_CENTER)


def goal_angle(p: Point) -> float:
    """Return the angle in radians subtended by the goal mouth as seen from a point."""
    dx = PITCH_LENGTH_M - p.x
    half_width = GOAL_WIDTH_M / 2
    left = math.atan2(GOAL_CENTER_Y_M + half_width - p.y, dx)
    right = math.atan2(GOAL_CENTER_Y_M - half_width - p.y, dx)
    return abs(left - right)


def clamp_to_pitch(p: Point) -> Point:
    """Return the point moved inside the pitch boundaries."""
    return Point(min(max(p.x, 0.0), PITCH_LENGTH_M), min(max(p.y, 0.0), PITCH_WIDTH_M))


def mirror(p: Point) -> Point:
    """Convert a point between the two teams' attacking perspectives."""
    return Point(PITCH_LENGTH_M - p.x, PITCH_WIDTH_M - p.y)
