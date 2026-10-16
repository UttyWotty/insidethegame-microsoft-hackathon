"""Immutable models for players, playing styles, and teams.

Player attributes and team style parameters are normalised to the range 0..1.
Team exposes lookup helpers used by the simulator and analytics layers.
"""

from dataclasses import asdict, dataclass

from insidegame.core.exceptions import RosterError
from insidegame.core.zones import Channel
from insidegame.domain.enums import Position


@dataclass(frozen=True)
class PlayerAttributes:
    """Normalised skill ratings that drive simulated outcomes."""

    pace: float
    passing: float
    finishing: float
    tackling: float


@dataclass(frozen=True)
class Player:
    """A fictional player in a squad."""

    player_id: str
    name: str
    shirt_number: int
    position: Position
    attributes: PlayerAttributes

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        data = asdict(self)
        data["position"] = self.position.value
        return data


@dataclass(frozen=True)
class TeamStyle:
    """Tactical tendencies of a team.

    directness: preference for long forward passes over short circulation.
    pressing: intensity of pressure applied without the ball.
    risk: willingness to shoot from lower-probability positions.
    weak_flank: the defensive flank (LEFT or RIGHT, in the team's own frame) that opponents tend to exploit.
    """

    label: str
    directness: float
    pressing: float
    risk: float
    weak_flank: Channel


@dataclass(frozen=True)
class Team:
    """A fictional club with its starting eleven and style."""

    team_id: str
    name: str
    short_name: str
    players: tuple[Player, ...]
    style: TeamStyle

    def players_in(self, position: Position) -> tuple[Player, ...]:
        """Return all players registered at the given position."""
        return tuple(p for p in self.players if p.position is position)

    def goalkeeper(self) -> Player:
        """Return the goalkeeper, raising RosterError when absent."""
        keepers = self.players_in(Position.GOALKEEPER)
        if not keepers:
            raise RosterError(f"Team {self.team_id} has no goalkeeper")
        return keepers[0]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "team_id": self.team_id,
            "name": self.name,
            "short_name": self.short_name,
            "style": asdict(self.style),
            "players": [p.to_dict() for p in self.players],
        }
