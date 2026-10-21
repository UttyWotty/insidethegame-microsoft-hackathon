"""Pure line-break assessment of a pass from the opponents' positions when it was played.

Opponents are converted to the passing team's attacking frame and grouped by position, goalkeeper excluded.
A pass bypasses the opponents it moves the ball beyond, and breaks a line only when it starts behind every
player in that line and ends beyond every one.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import Position, Side
from insidegame.domain.match import MatchMetadata


class DefensiveLine(StrEnum):
    """An opponent line a pass can break."""

    MIDFIELD = "midfield"
    DEFENCE = "defence"


LINE_POSITIONS: dict[DefensiveLine, Position] = {
    DefensiveLine.MIDFIELD: Position.MIDFIELDER, DefensiveLine.DEFENCE: Position.DEFENDER,
}


@dataclass(frozen=True)
class LineBreak:
    """How many opponents a pass took out of the game and which lines it broke (midfield before defence)."""

    opponents_bypassed: int
    lines_broken: tuple[DefensiveLine, ...]

    @property
    def breaks_line(self) -> bool:
        """Whether the pass broke at least one line."""
        return bool(self.lines_broken)


def opponent_lines(team_id: str, metadata: MatchMetadata,
                   positions_home: Mapping[str, Point]) -> dict[Position, list[Point]]:
    """Outfield opponents of team_id grouped by position, in team_id's attacking frame.

    positions_home holds absolute home-frame positions keyed by player id; players missing from it are skipped.
    """
    side = metadata.side_of(team_id)
    opponents = metadata.team(side.opponent)
    lines: dict[Position, list[Point]] = {}
    for player in opponents.players:
        point = positions_home.get(player.player_id)
        if point is None or player.position is Position.GOALKEEPER:
            continue
        lines.setdefault(player.position, []).append(point if side is Side.HOME else mirror(point))
    return lines


def opponents_goal_side(x: float, lines: Mapping[Position, Sequence[Point]]) -> int:
    """Number of outfield opponents nearer the attacked goal than x."""
    return sum(1 for points in lines.values() for p in points if p.x > x)


def assess_line_break(start: Point, end: Point, lines: Mapping[Position, Sequence[Point]]) -> LineBreak | None:
    """Assess a pass from start to end against the opponent lines; None when no opponent positions are known."""
    if not any(lines.values()):
        return None
    bypassed = max(opponents_goal_side(start.x, lines) - opponents_goal_side(end.x, lines), 0)
    broken = tuple(line for line, position in LINE_POSITIONS.items()
                   if (points := lines.get(position)) and start.x < min(p.x for p in points)
                   and end.x > max(p.x for p in points))
    return LineBreak(bypassed, broken)
