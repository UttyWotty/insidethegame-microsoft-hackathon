"""Synthetic player tracking: formation-aware positions for all 22 players after every event.

Teams in possession push up and spread; teams out of possession compact, shift toward the ball, and press higher
when their style says so. Players involved in the event are placed exactly, and a small deterministic sway keeps
movement natural. Positions are returned in the absolute home frame (home attacking toward x = 105).
"""

import math
from dataclasses import dataclass, field

from insidegame.core.constants import GOAL_CENTER_Y_M, PITCH_LENGTH_M, PITCH_WIDTH_M
from insidegame.core.geometry import PITCH_CENTER, Point, clamp_to_pitch, distance, mirror
from insidegame.domain.enums import EventType, Outcome, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Team
from insidegame.tracking.formation import DEFENDER_INDICES, FORWARD_INDICES, GOALKEEPER_INDEX, SLOTS

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

Frame = list[tuple[str, float, float]]


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

    def _to_home(self, point: Point, side: Side) -> Point:
        return point if side is Side.HOME else mirror(point)

    def _update_ball(self, event: MatchEvent) -> None:
        if event.event_type in (EventType.KICK_OFF, EventType.POSSESSION_CHANGE) and event.team_id:
            self.possessing = self.metadata.side_of(event.team_id)
        location = event.end or event.start
        if location is not None and event.team_id is not None:
            self.ball_home_frame = self._to_home(location, self.metadata.side_of(event.team_id))

    def _pin_actors(self, event: MatchEvent, positions: dict[str, Point]) -> None:
        if event.team_id is None:
            return
        side = self.metadata.side_of(event.team_id)
        if event.player_id and event.start:
            anchor = event.end if event.event_type is EventType.CARRY and event.end else event.start
            positions[event.player_id] = self._to_home(anchor, side)
        if event.receiver_id and event.end and event.outcome is Outcome.SUCCESS:
            positions[event.receiver_id] = self._to_home(event.end, side)

    def _close_down(self, positions: dict[str, Point], event: MatchEvent) -> None:
        defending = self.metadata.team(self.possessing.opponent)
        candidates = [p.player_id for p in defending.players if p.player_id != event.player_id]
        nearest = min(candidates, key=lambda pid: distance(positions[pid], self.ball_home_frame))
        ball, current = self.ball_home_frame, positions[nearest]
        gap = distance(current, ball)
        if gap > CLOSE_DOWN_M:
            ratio = (gap - CLOSE_DOWN_M) / gap
            positions[nearest] = Point(current.x + (ball.x - current.x) * ratio, current.y + (ball.y - current.y) * ratio)

    def frame(self, event: MatchEvent) -> Frame:
        """Return [player_id, x, y] for all 22 players after the event, in the absolute home frame."""
        self._update_ball(event)
        positions: dict[str, Point] = {}
        for side in (Side.HOME, Side.AWAY):
            team = self.metadata.team(side)
            ball = self._to_home(self.ball_home_frame, side)
            for player, point in zip(team.players, _shape(team, ball, side is self.possessing, event.sequence),
                                     strict=True):
                positions[player.player_id] = self._to_home(point, side)
        self._close_down(positions, event)
        self._pin_actors(event, positions)
        return [(pid, round(min(max(p.x, 0.0), PITCH_LENGTH_M), POSITION_DECIMALS),
                 round(min(max(p.y, 0.0), PITCH_WIDTH_M), POSITION_DECIMALS)) for pid, p in positions.items()]
