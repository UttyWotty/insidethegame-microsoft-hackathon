"""Pure kinematics that keep synthetic player movement within human limits.

Each player's top speed comes from their pace rating, and a step toward a target position is capped at what that
speed allows in the elapsed match time, so nobody covers ground faster than a real footballer. Speeds are measured
from consecutive positions and players above the high-intensity sprint threshold are reported for live tags.
"""

from collections.abc import Mapping

from insidegame.core.geometry import Point, distance

MS_TO_KMH: float = 3.6
BASE_TOP_SPEED_KMH: float = 27.0
PACE_TOP_SPEED_KMH: float = 8.0
SPRINT_KMH: float = 25.2
SPEED_DECIMALS: int = 1


def top_speed_kmh(pace: float) -> float:
    """Top running speed for a pace rating in 0..1: about 27 km/h for the slowest, 35 km/h for the fastest."""
    return BASE_TOP_SPEED_KMH + PACE_TOP_SPEED_KMH * min(max(pace, 0.0), 1.0)


def step_toward(current: Point, target: Point, max_speed_kmh: float, elapsed_s: float) -> Point:
    """Move from current toward target, covering at most what max_speed_kmh allows in elapsed_s seconds."""
    reach = max(elapsed_s, 0.0) * max_speed_kmh / MS_TO_KMH
    gap = distance(current, target)
    if gap <= reach:
        return target
    ratio = reach / gap
    return Point(current.x + (target.x - current.x) * ratio, current.y + (target.y - current.y) * ratio)


def timed_target(current: Point, destination: Point, elapsed_s: float, remaining_s: float) -> Point:
    """Where a player should be after elapsed_s to reach destination exactly when remaining_s has passed."""
    if remaining_s <= elapsed_s or remaining_s <= 0.0:
        return destination
    ratio = max(elapsed_s, 0.0) / remaining_s
    return Point(current.x + (destination.x - current.x) * ratio, current.y + (destination.y - current.y) * ratio)


def speed_kmh(before: Point, after: Point, elapsed_s: float) -> float:
    """Average speed between two positions; zero when no time has passed."""
    if elapsed_s <= 0.0:
        return 0.0
    return distance(before, after) / elapsed_s * MS_TO_KMH


def fastest_sprinter(speeds: Mapping[str, float]) -> tuple[str, float] | None:
    """The fastest player at or above SPRINT_KMH with their rounded speed, or None when nobody is sprinting."""
    if not speeds:
        return None
    player, top = max(speeds.items(), key=lambda item: item[1])
    if top < SPRINT_KMH:
        return None
    return player, round(top, SPEED_DECIMALS)
