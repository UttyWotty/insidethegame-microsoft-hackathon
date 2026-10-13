"""Synthetic player tracking: formation-aware positions for all 22 players after every event.

Teams in possession push up and spread; teams out of possession compact, shift toward the ball, and press higher
when their style says so. Players involved in the event are targeted at the ball, players about to act start
running so they arrive on time, and a small deterministic sway keeps movement natural. Every player moves toward their target no faster than their pace-based top speed allows in
the elapsed match time (formations reset at kick-offs), the fastest sprinter of each frame is reported, and each
player's distance covered and top speed accumulate for the physical leaderboard.
Positions are returned in the absolute home frame (home attacking toward x = 105).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from insidegame.core.constants import GOAL_CENTER_Y_M, PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import PITCH_CENTER, Point, clamp_to_pitch, distance, mirror
from insidegame.domain.enums import EventType, Outcome, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.tracking.formation import DEFENDER_INDICES, FORWARD_INDICES, GOALKEEPER_INDEX, SLOTS
from insidegame.tracking.motion import fastest_sprinter, speed_kmh, step_toward, timed_target, top_speed_kmh

POSITION_DECIMALS: int = 1
ATTACK_PIVOT_X: float = 45.0
ATTACK_PUSH_FACTOR: float = 0.55
ATTACK_PUSH_RANGE: tuple[float, float] = (-10.0, 30.0)
ATTACK_WIDTH: float = 1.15
DEFEND_PIVOT_X: float = 60.0
DEFEND_PUSH_FACTOR: float = 0.5
DEFEND_PUSH_RANGE: tuple[float, float] = (-20.0, 18.0)
DEFEND_WIDTH: float = 0.75
DEFEND_BALL_SHIFT: float = 0.35
PRESSING_HEIGHT_M: float = 6.0
DEFENDER_LINE_FACTOR: float = 0.8
FORWARD_DEFENDING_FACTOR: float = 0.7
KEEPER_BASE_X: float = 4.0
KEEPER_STEP: float = 0.08
KEEPER_MAX_STEP_M: float = 12.0
KEEPER_FOLLOW_Y: float = 0.25
CLOSE_DOWN_M: float = 2.5
SWAY_M: float = 1.2
SWAY_SEQUENCE_PRIME: int = 37
SWAY_INDEX_PRIME: int = 101
LOOKAHEAD_S: float = 8.0
LOOKAHEAD_EVENTS: int = 12
OFF_BALL_PACE: float = 0.75
M_PER_KM: float = 1000.0
PHYSICAL_DECIMALS: int = 2

Frame = list[tuple[str, float, float]]
Sprint = tuple[str, float]


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    return min(max(value, bounds[0]), bounds[1])


def _sway(sequence: int, index: int) -> tuple[float, float]:
    angle = (sequence * SWAY_SEQUENCE_PRIME + index * SWAY_INDEX_PRIME) % 360
    return SWAY_M * math.cos(math.radians(angle)), SWAY_M * math.sin(math.radians(angle))


def _shape(team: Team, ball: Point, in_possession: bool, sequence: int) -> list[Point]:
    """Formation positions for one team in its own attacking frame."""
    if in_possession:
        push, width, y_shift = _clamp((ball.x - ATTACK_PIVOT_X) * ATTACK_PUSH_FACTOR, ATTACK_PUSH_RANGE), ATTACK_WIDTH, 0.0
    else:
        push = _clamp((ball.x - DEFEND_PIVOT_X) * DEFEND_PUSH_FACTOR, DEFEND_PUSH_RANGE) + team.style.pressing * PRESSING_HEIGHT_M
        width, y_shift = DEFEND_WIDTH, DEFEND_BALL_SHIFT * (ball.y - GOAL_CENTER_Y_M)
    points = []
    for index, slot in enumerate(SLOTS):
        if index == GOALKEEPER_INDEX:
            keeper_x = KEEPER_BASE_X + min(ball.x * KEEPER_STEP, KEEPER_MAX_STEP_M)
            points.append(Point(keeper_x, GOAL_CENTER_Y_M + (ball.y - GOAL_CENTER_Y_M) * KEEPER_FOLLOW_Y))
            continue
        factor = DEFENDER_LINE_FACTOR if index in DEFENDER_INDICES else (
            FORWARD_DEFENDING_FACTOR if index in FORWARD_INDICES and not in_possession else 1.0)
        dx, dy = _sway(sequence, index)
        x = slot.x + push * factor + dx
        y = GOAL_CENTER_Y_M + (slot.y - GOAL_CENTER_Y_M) * width + y_shift + dy
        points.append(clamp_to_pitch(Point(x, y)))
    return points


@dataclass
class TrackingModel:
    """Stateful generator of 22-player frames for one match."""

    metadata: MatchMetadata
    possessing: Side = Side.HOME
    ball_home_frame: Point = field(default_factory=lambda: PITCH_CENTER)
    previous: dict[str, Point] = field(default_factory=dict)
    clock: tuple[int, float] = (0, 0.0)
    top_speeds: dict[str, float] = field(default_factory=dict)
    sprint: Sprint | None = None
    covered_m: dict[str, float] = field(default_factory=dict)
    fastest_kmh: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.top_speeds = {p.player_id: top_speed_kmh(p.attributes.pace)
                           for team in (self.metadata.home, self.metadata.away) for p in team.players}

    def _to_home(self, point: Point, side: Side) -> Point:
        return point if side is Side.HOME else mirror(point)

    def _update_ball(self, event: MatchEvent) -> None:
        if event.event_type in (EventType.KICK_OFF, EventType.POSSESSION_CHANGE) and event.team_id:
            self.possessing = self.metadata.side_of(event.team_id)
        location = event.end or event.start
        if location is not None and event.team_id is not None:
            self.ball_home_frame = self._to_home(location, self.metadata.side_of(event.team_id))

    def _pin_actors(self, event: MatchEvent, positions: dict[str, Point]) -> set[str]:
        """Target the event's actor and successful receiver at the ball; returns who was pinned."""
        if event.team_id is None:
            return set()
        pinned: set[str] = set()
        side = self.metadata.side_of(event.team_id)
        if event.player_id and event.start:
            anchor = event.end if event.event_type is EventType.CARRY and event.end else event.start
            positions[event.player_id] = self._to_home(anchor, side)
            pinned.add(event.player_id)
        if event.receiver_id and event.end and event.outcome is Outcome.SUCCESS:
            positions[event.receiver_id] = self._to_home(event.end, side)
            pinned.add(event.receiver_id)
        return pinned

    def _anticipate(self, event: MatchEvent, upcoming: Sequence[MatchEvent], positions: dict[str, Point],
                    involved: set[str]) -> None:
        """Start players toward actions they take within LOOKAHEAD_S, timed to arrive as the action happens."""
        if not self.previous or event.period != self.clock[0]:
            return
        elapsed = event.match_second - self.clock[1]
        for later in upcoming:
            ahead = later.match_second - event.match_second
            if later.period != event.period or ahead > LOOKAHEAD_S:
                return
            pid = later.player_id
            if pid is None or pid in involved or later.start is None or later.team_id is None:
                continue
            destination = self._to_home(later.start, self.metadata.side_of(later.team_id))
            positions[pid] = timed_target(self.previous[pid], destination, elapsed, elapsed + ahead)
            involved.add(pid)

    def _close_down(self, positions: dict[str, Point], event: MatchEvent) -> None:
        defending = self.metadata.team(self.possessing.opponent)
        candidates = [p.player_id for p in defending.players if p.player_id != event.player_id]
        nearest = min(candidates, key=lambda pid: distance(positions[pid], self.ball_home_frame))
        ball, current = self.ball_home_frame, positions[nearest]
        gap = distance(current, ball)
        if gap > CLOSE_DOWN_M:
            ratio = (gap - CLOSE_DOWN_M) / gap
            positions[nearest] = Point(current.x + (ball.x - current.x) * ratio, current.y + (ball.y - current.y) * ratio)

    def _cap(self, player_id: str, involved: set[str]) -> float:
        """Speed limit: full top speed on or toward the ball, OFF_BALL_PACE of it while holding shape."""
        top = self.top_speeds[player_id]
        return top if player_id in involved else top * OFF_BALL_PACE

    def _move(self, event: MatchEvent, targets: dict[str, Point], involved: set[str]) -> dict[str, Point]:
        """Cap each player's step at their speed limit; kick-offs and new periods reset to the targets.

        Sprint tags consider only the involved players, those on or about to reach the ball.
        """
        elapsed = event.match_second - self.clock[1]
        if event.event_type is EventType.KICK_OFF or event.period != self.clock[0] or not self.previous:
            moved, speeds = dict(targets), {}
        else:
            moved = {pid: step_toward(self.previous[pid], target, self._cap(pid, involved), elapsed)
                     for pid, target in targets.items()}
            speeds = {pid: speed_kmh(self.previous[pid], point, elapsed) for pid, point in moved.items()}
        for pid, point in moved.items():
            if pid in speeds:
                self.covered_m[pid] = self.covered_m.get(pid, 0.0) + distance(self.previous[pid], point)
                self.fastest_kmh[pid] = max(self.fastest_kmh.get(pid, 0.0), speeds[pid])
        self.previous, self.clock = moved, (event.period, event.match_second)
        self.sprint = fastest_sprinter({pid: v for pid, v in speeds.items() if pid in involved})
        return moved

    def physical(self) -> dict[str, dict[str, float]]:
        """Distance covered (km) and top speed (km/h) so far for every player who has moved."""
        return {pid: {"distance_km": round(self.covered_m[pid] / M_PER_KM, PHYSICAL_DECIMALS),
                      "top_kmh": round(self.fastest_kmh.get(pid, 0.0), 1)} for pid in self.covered_m}

    def frame(self, event: MatchEvent, upcoming: Sequence[MatchEvent] = ()) -> Frame:
        """Return [player_id, x, y] for all 22 players after the event, in the absolute home frame.

        upcoming (default empty) lists the next events, oldest first, so players can start toward their next action.
        After each call, sprint holds the fastest involved player at sprint speed with their km/h, or None.
        """
        self._update_ball(event)
        positions: dict[str, Point] = {}
        for side in (Side.HOME, Side.AWAY):
            team = self.metadata.team(side)
            ball = self._to_home(self.ball_home_frame, side)
            for player, point in zip(team.players, _shape(team, ball, side is self.possessing, event.sequence),
                                     strict=True):
                positions[player.player_id] = self._to_home(point, side)
        self._close_down(positions, event)
        involved = self._pin_actors(event, positions)
        self._anticipate(event, upcoming, positions, involved)
        positions = self._move(event, positions, involved)
        return [(pid, round(min(max(p.x, 0.0), PITCH_LENGTH_M), POSITION_DECIMALS),
                 round(min(max(p.y, 0.0), PITCH_WIDTH_M), POSITION_DECIMALS)) for pid, p in positions.items()]
