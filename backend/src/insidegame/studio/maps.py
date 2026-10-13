"""Pure event-based studio maps: where each team has the ball, where it presses, and how it passes.

Heat and pressing maps count event locations on a coarse grid and scale them to 0..1 so the busiest cell is 1.
The pass network places each player at the average spot of their completed passes and links pairs that combined
at least MIN_LINK_PASSES times. Event coordinates arrive in the acting team's frame and are converted to the
absolute home frame.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from insidegame.core.constants import PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import Point, mirror
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent

GRID_COLS: int = 12
GRID_ROWS: int = 8
MIN_LINK_PASSES: int = 3
VALUE_DECIMALS: int = 2
POSITION_DECIMALS: int = 1
ON_BALL: frozenset[EventType] = frozenset({EventType.PASS, EventType.CARRY, EventType.SHOT})
DEFENSIVE: frozenset[EventType] = frozenset({EventType.PRESSURE, EventType.TACKLE, EventType.INTERCEPTION})

Grid = list[list[float]]


@dataclass(frozen=True)
class NetworkNode:
    """A player in a pass network: average pass position and passes involved in."""

    player_id: str
    x: float
    y: float
    passes: int


@dataclass(frozen=True)
class PassNetwork:
    """One team's completed-pass network."""

    nodes: list[NetworkNode] = field(default_factory=list)
    links: list[tuple[str, str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"nodes": [n.__dict__ for n in self.nodes], "links": [list(link) for link in self.links]}


def absolute(point: Point, team_is_home: bool) -> Point:
    """Convert a point from the acting team's frame to the absolute home frame."""
    return point if team_is_home else mirror(point)


def _cell(point: Point) -> tuple[int, int]:
    col = min(int(point.x / PITCH_LENGTH_M * GRID_COLS), GRID_COLS - 1)
    row = min(int(point.y / PITCH_WIDTH_M * GRID_ROWS), GRID_ROWS - 1)
    return max(col, 0), max(row, 0)


def density(events: Iterable[MatchEvent], team_id: str, home_id: str, kinds: frozenset[EventType]) -> Grid:
    """Rows x columns grid of the team's events of these kinds, scaled so the busiest cell is 1."""
    counts: Counter[tuple[int, int]] = Counter()
    for event in events:
        if event.team_id == team_id and event.event_type in kinds and event.start is not None:
            counts[_cell(absolute(event.start, team_id == home_id))] += 1
    peak = max(counts.values(), default=0)
    return [[round(counts[(c, r)] / peak, VALUE_DECIMALS) if peak else 0.0 for c in range(GRID_COLS)]
            for r in range(GRID_ROWS)]


def pass_network(events: Iterable[MatchEvent], team_id: str, home_id: str) -> PassNetwork:
    """Completed-pass network: average pass position per passer and links of MIN_LINK_PASSES or more."""
    spots: dict[str, list[Point]] = defaultdict(list)
    pairs: Counter[tuple[str, str]] = Counter()
    for event in events:
        if (event.team_id != team_id or event.event_type is not EventType.PASS or event.outcome is not Outcome.SUCCESS
                or not event.player_id or not event.receiver_id or event.start is None):
            continue
        spots[event.player_id].append(absolute(event.start, team_id == home_id))
        pairs[tuple(sorted((event.player_id, event.receiver_id)))] += 1  # type: ignore[index]
    nodes = [NetworkNode(pid, round(sum(p.x for p in pts) / len(pts), POSITION_DECIMALS),
                         round(sum(p.y for p in pts) / len(pts), POSITION_DECIMALS), len(pts))
             for pid, pts in spots.items()]
    known = {n.player_id for n in nodes}
    links = sorted(((a, b, n) for (a, b), n in pairs.items() if n >= MIN_LINK_PASSES and {a, b} <= known),
                   key=lambda link: -link[2])
    return PassNetwork(sorted(nodes, key=lambda n: -n.passes), links)
