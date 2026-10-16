"""Pure team-shape metrics from one positions map: back-line height, length, width, and compactness.

Positions arrive in the absolute home frame and the away team is mirrored into its own frame, so every metric is
measured in metres from the team's own goal line whichever end it defends.
The back-line height also gives a high, mid, or low block label through named thresholds.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import Position
from insidegame.domain.teams import Team

HIGH_BLOCK_MIN_M: float = 33.0
LOW_BLOCK_MAX_M: float = 24.0
SHAPE_DECIMALS: int = 1
MIN_OUTFIELD_PLAYERS: int = 2


class Block(StrEnum):
    """How high a team defends, from its back-line height."""

    HIGH = "high"
    MID = "mid"
    LOW = "low"


def block_for(line_height_m: float) -> Block:
    """HIGH at or above HIGH_BLOCK_MIN_M, LOW below LOW_BLOCK_MAX_M, MID otherwise."""
    if line_height_m >= HIGH_BLOCK_MIN_M:
        return Block.HIGH
    return Block.LOW if line_height_m < LOW_BLOCK_MAX_M else Block.MID


@dataclass(frozen=True)
class ShapeMetrics:
    """One team's shape in its own frame, in metres.

    line_height_m is the mean x of the defenders (distance from the own goal line); length_m and width_m are the
    x and y spans of the outfield players; compactness_m is their mean distance from their centroid.
    """

    line_height_m: float
    length_m: float
    width_m: float
    compactness_m: float

    @property
    def block(self) -> Block:
        """The block label for this back-line height."""
        return block_for(self.line_height_m)

    def to_dict(self) -> dict[str, object]:
        """Return the four metrics rounded to SHAPE_DECIMALS, plus the block label."""
        return {"line_height_m": round(self.line_height_m, SHAPE_DECIMALS),
                "length_m": round(self.length_m, SHAPE_DECIMALS), "width_m": round(self.width_m, SHAPE_DECIMALS),
                "compactness_m": round(self.compactness_m, SHAPE_DECIMALS), "block": self.block.value}


def _own_frame(point: Point, is_home: bool) -> Point:
    return point if is_home else mirror(point)


def team_shape(team: Team, positions_home: Mapping[str, Point], is_home: bool) -> ShapeMetrics | None:
    """Measure a team's shape, or None when any defender or fewer than two outfield players are in the map."""
    defenders = team.players_in(Position.DEFENDER)
    if not defenders or any(p.player_id not in positions_home for p in defenders):
        return None
    outfield = [_own_frame(positions_home[p.player_id], is_home) for p in team.players
                if p.position is not Position.GOALKEEPER and p.player_id in positions_home]
    if len(outfield) < MIN_OUTFIELD_PLAYERS:
        return None
    line = sum(_own_frame(positions_home[p.player_id], is_home).x for p in defenders) / len(defenders)
    xs, ys = [p.x for p in outfield], [p.y for p in outfield]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    compactness = sum(math.hypot(p.x - cx, p.y - cy) for p in outfield) / len(outfield)
    return ShapeMetrics(line, max(xs) - min(xs), max(ys) - min(ys), compactness)
