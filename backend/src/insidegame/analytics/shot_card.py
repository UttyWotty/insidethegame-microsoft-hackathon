"""Pure shot card for broadcast graphics: where a shot went in the goal frame, how hard, from where, and the keeper.

The simulator decides only the outcome of a shot, so the placement in the goal mouth and the goalkeeper's dive are
derived deterministically from the event id with a local random generator, consistent with the outcome: goals
beat the keeper inside the frame, saves meet the keeper, misses finish wide (on the side the shot trace shows) or
over. The match simulation's own random sequence is untouched, so seeded matches are unchanged.
"""

import math
import random
import zlib
from dataclasses import dataclass

from insidegame.core.constants import GOAL_CENTER_Y_M, GOAL_WIDTH_M
from insidegame.core.geometry import distance_to_goal, goal_angle
from insidegame.domain.enums import ShotResult
from insidegame.domain.events import MatchEvent

GOAL_HEIGHT_M: float = 2.44
POST_MARGIN_M: float = 0.25
BAR_MARGIN_M: float = 0.2
CORNER_SPEED_KMH: float = 100.0
WIDE_MAX_M: float = 2.2
OVER_MAX_M: float = 1.2
OVER_SHARE: float = 0.4
SAVE_HEIGHT_M: float = 1.9
BEATEN_REACH: float = 0.45
DECIMALS: int = 2


@dataclass(frozen=True)
class ShotCard:
    """Broadcast facts for one shot. Placement and keeper_y are metres from the goal centre, positive to the
    shooter's right; placement_z is height. Placement fields are None for blocked shots."""

    result: str
    xg: float
    speed_kmh: float | None
    distance_m: float
    angle_deg: float
    placement_y: float | None
    placement_z: float | None
    keeper_y: float | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return dict(self.__dict__)


def _placement(event: MatchEvent, rng: random.Random) -> tuple[float, float, float] | None:
    """Placement (y, z) and keeper dive y consistent with the shot result, or None for blocks."""
    half = GOAL_WIDTH_M / 2
    inside = half - POST_MARGIN_M
    result = event.shot_result
    if result is ShotResult.GOAL:
        corner = (event.ball_speed_kmh or 0.0) >= CORNER_SPEED_KMH
        y = rng.choice((-1.0, 1.0)) * (rng.uniform(inside * 0.55, inside) if corner else rng.uniform(0.0, inside))
        z = (GOAL_HEIGHT_M - BAR_MARGIN_M) * rng.random() ** 1.5
        keeper = y * BEATEN_REACH if rng.random() < 0.5 else -math.copysign(rng.uniform(0.5, 2.0), y)
        return y, z, keeper
    if result is ShotResult.SAVED:
        y = rng.uniform(-inside, inside)
        return y, SAVE_HEIGHT_M * rng.random(), y
    if result is ShotResult.OFF_TARGET:
        side = 1.0 if event.end is not None and event.end.y >= GOAL_CENTER_Y_M else -1.0
        if rng.random() < OVER_SHARE:
            return rng.uniform(-inside, inside), GOAL_HEIGHT_M + rng.uniform(0.2, OVER_MAX_M), 0.0
        return side * (half + rng.uniform(0.3, WIDE_MAX_M)), rng.uniform(0.0, GOAL_HEIGHT_M), side * 0.8
    return None


def shot_card(event: MatchEvent, xg: float) -> ShotCard:
    """Build the shot card for a shot event (it must have a start location)."""
    assert event.start is not None
    rng = random.Random(zlib.crc32(event.event_id.encode()))
    placed = _placement(event, rng)
    y, z, keeper = placed if placed else (None, None, None)
    return ShotCard(
        (event.shot_result or ShotResult.OFF_TARGET).value, round(xg, DECIMALS),
        round(event.ball_speed_kmh, 1) if event.ball_speed_kmh else None,
        round(distance_to_goal(event.start), 1), round(math.degrees(goal_angle(event.start)), 1),
        None if y is None else round(y, DECIMALS), None if z is None else round(z, DECIMALS),
        None if keeper is None else round(keeper, DECIMALS))
