"""Pure space control from one tracking frame: which team owns each part of the pitch.

Each cell of a grid belongs to the team of the nearest player, a simple Voronoi model of pitch control. The result
reports the owner of every cell and each team's share of the whole pitch and of the home side's defensive,
middle, and attacking thirds (measured along the absolute home frame).
"""

import math
from dataclasses import dataclass

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M

CONTROL_COLS: int = 21
CONTROL_ROWS: int = 14
THIRDS: int = 3
PERCENT: float = 100.0
SHARE_DECIMALS: int = 1
HOME: int = 1
AWAY: int = -1


@dataclass(frozen=True)
class SpaceControl:
    """Cell owners (1 home, -1 away) and home shares of the pitch and of each third, in percent."""

    owners: list[list[int]]
    home_share: float
    home_thirds: tuple[float, float, float]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"owners": self.owners, "home_share": self.home_share, "home_thirds": list(self.home_thirds)}


def space_control(positions: list[tuple[str, float, float]], home_ids: frozenset[str]) -> SpaceControl:
    """Assign each grid cell to the team of the nearest player and summarise the shares."""
    cell_w, cell_h = PITCH_LENGTH_M / CONTROL_COLS, PITCH_WIDTH_M / CONTROL_ROWS
    owners: list[list[int]] = []
    for row in range(CONTROL_ROWS):
        y = (row + 0.5) * cell_h
        line = []
        for col in range(CONTROL_COLS):
            x = (col + 0.5) * cell_w
            nearest = min(positions, key=lambda p: math.hypot(p[1] - x, p[2] - y))
            line.append(HOME if nearest[0] in home_ids else AWAY)
        owners.append(line)
    per_third = CONTROL_COLS / THIRDS
    thirds = []
    for third in range(THIRDS):
        cols = [c for c in range(CONTROL_COLS) if int(c // per_third) == third]
        cells = [owners[r][c] for r in range(CONTROL_ROWS) for c in cols]
        thirds.append(round(PERCENT * sum(v == HOME for v in cells) / len(cells), SHARE_DECIMALS))
    total = [v for line in owners for v in line]
    share = round(PERCENT * sum(v == HOME for v in total) / len(total), SHARE_DECIMALS)
    return SpaceControl(owners, share, (thirds[0], thirds[1], thirds[2]))
