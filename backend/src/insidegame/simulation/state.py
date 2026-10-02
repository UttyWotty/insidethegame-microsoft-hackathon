"""Mutable simulation state and the event emitter used by the match engine.

SimState tracks clock, possession, ball location, carrier, and score while a match is simulated.
emit appends a MatchEvent stamped with the current clock, possession, and score snapshot.
"""

import random
from dataclasses import dataclass, field

from insidegame.core.geometry import PITCH_CENTER, Point
from insidegame.domain.enums import EventType, Outcome, Position, ShotResult, Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata
from insidegame.domain.teams import Player, Team

FIRST_PERIOD: int = 1
INITIAL_POSSESSION_ID: int = 0


@dataclass
class SimState:
    """Everything the engine needs to continue a match from the current moment."""

    metadata: MatchMetadata
    rng: random.Random
    attacking: Side
    carrier: Player
    ball: Point
    period: int = FIRST_PERIOD
    clock_s: float = 0.0
    possession_id: int = INITIAL_POSSESSION_ID
    under_pressure: bool = False
    home_goals: int = 0
    away_goals: int = 0
    events: list[MatchEvent] = field(default_factory=list)

    @classmethod
    def new(cls, metadata: MatchMetadata) -> "SimState":
        """Create the pre-kickoff state with the home side in possession."""
        forward = metadata.home.players_in(Position.FORWARD)[0]
        return cls(metadata, random.Random(metadata.seed), Side.HOME, forward, PITCH_CENTER)

    @property
    def attacking_team(self) -> Team:
        """Team currently in possession."""
        return self.metadata.team(self.attacking)

    @property
    def defending_team(self) -> Team:
        """Team currently out of possession."""
        return self.metadata.team(self.attacking.opponent)

    def goal_difference(self, side: Side) -> int:
        """Goals scored minus conceded from the perspective of side."""
        diff = self.home_goals - self.away_goals
        return diff if side is Side.HOME else -diff

    def advance(self, seconds: float) -> None:
        """Move the match clock forward."""
        self.clock_s += seconds

    def add_goal(self, side: Side) -> None:
        """Increment the score for a side."""
        if side is Side.HOME:
            self.home_goals += 1
        else:
            self.away_goals += 1

    def emit(
        self, event_type: EventType, side: Side | None, player: Player | None, start: Point | None, *,
        end: Point | None = None, outcome: Outcome | None = None, receiver_id: str | None = None,
        opponent_id: str | None = None, under_pressure: bool = False, length_m: float | None = None,
        ball_speed_kmh: float | None = None, shot_result: ShotResult | None = None,
    ) -> MatchEvent:
        """Record an event at the current clock; coordinates must be in the acting side's frame."""
        sequence = len(self.events)
        event = MatchEvent(
            event_id=f"{self.metadata.match_id}-{sequence:05d}",
            match_id=self.metadata.match_id,
            sequence=sequence,
            period=self.period,
            match_second=self.clock_s,
            event_type=event_type,
            team_id=self.metadata.team(side).team_id if side else None,
            player_id=player.player_id if player else None,
            possession_id=self.possession_id,
            start=start,
            score_home=self.home_goals,
            score_away=self.away_goals,
            end=end, outcome=outcome, receiver_id=receiver_id, opponent_id=opponent_id,
            under_pressure=under_pressure, length_m=length_m, ball_speed_kmh=ball_speed_kmh,
            shot_result=shot_result,
        )
        self.events.append(event)
        return event

    def give_possession(self, side: Side, carrier: Player, ball: Point) -> None:
        """Hand the ball to side at ball (in that side's frame) and emit a possession change."""
        self.attacking = side
        self.carrier = carrier
        self.ball = ball
        self.under_pressure = False
        self.possession_id += 1
        self.emit(EventType.POSSESSION_CHANGE, side, carrier, ball)
