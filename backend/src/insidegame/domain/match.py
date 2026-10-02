"""Immutable models describing a fixture and a completed simulated match.

MatchMetadata carries everything needed to reproduce a match, including the seed.
MatchResult bundles metadata with the ordered event stream and final score.
"""

from dataclasses import dataclass

from insidegame.domain.enums import Side
from insidegame.domain.events import MatchEvent
from insidegame.domain.teams import Team


@dataclass(frozen=True)
class MatchMetadata:
    """Static fixture information."""

    match_id: str
    competition: str
    venue: str
    kickoff_utc: str
    home: Team
    away: Team
    seed: int

    def team(self, side: Side) -> Team:
        """Return the team playing on the given side."""
        return self.home if side is Side.HOME else self.away

    def side_of(self, team_id: str) -> Side:
        """Return the side for a team identifier."""
        return Side.HOME if team_id == self.home.team_id else Side.AWAY

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {
            "match_id": self.match_id,
            "competition": self.competition,
            "venue": self.venue,
            "kickoff_utc": self.kickoff_utc,
            "seed": self.seed,
            "home": self.home.to_dict(),
            "away": self.away.to_dict(),
        }


@dataclass(frozen=True)
class MatchResult:
    """A fully simulated match."""

    metadata: MatchMetadata
    events: tuple[MatchEvent, ...]
    home_goals: int
    away_goals: int
