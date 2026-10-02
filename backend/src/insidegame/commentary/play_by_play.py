"""Deterministic play-by-play commentary generated from interpreted events.

Lines cover kick-offs, period ends, attacks into the final third, long passes, dribbles, tackles, interceptions,
high pressing, and sustained possession, paced by a minimum gap so the feed stays readable.
"""

from dataclasses import dataclass, field

from insidegame.analytics.analyzer import AnalysisUpdate
from insidegame.core.clock import minute_label
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.match import MatchMetadata

MIN_GAP_S: float = 50.0
LONG_PASS_M: float = 35.0
LONG_CARRY_M: float = 12.0
HIGH_PRESS_X_M: float = 70.0
ATTACKING_HALF_X_M: float = 52.5
SPELL_PASSES: int = 8


@dataclass(frozen=True)
class CommentaryLine:
    """One play-by-play line."""

    line_id: str
    period: int
    match_second: float
    minute: str
    text: str
    kind: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return dict(self.__dict__)


def _pick(options: tuple[str, ...], sequence: int) -> str:
    return options[sequence % len(options)]


@dataclass
class PlayByPlay:
    """Turns analysis updates into paced commentary lines for one match."""

    metadata: MatchMetadata
    names: dict[str, str] = field(default_factory=dict)
    teams: dict[str, str] = field(default_factory=dict)
    last_line_s: float | None = None
    spell: tuple[int, int] = (-1, 0)
    restart: str = "first_half"

    def __post_init__(self) -> None:
        for team in (self.metadata.home, self.metadata.away):
            self.teams[team.team_id] = team.name
            self.names.update({p.player_id: p.name for p in team.players})

    def _name(self, player_id: str | None) -> str:
        return self.names.get(player_id or "", "")

    def _line(self, update: AnalysisUpdate, text: str, kind: str, paced: bool = True) -> CommentaryLine | None:
        event = update.event
        if paced and self.last_line_s is not None and event.match_second - self.last_line_s < MIN_GAP_S:
            return None
        self.last_line_s = event.match_second
        return CommentaryLine(f"{event.event_id}-pbp", event.period, event.match_second,
                              minute_label(event.match_second, event.period), text, kind)

    def _flow(self, update: AnalysisUpdate) -> str | None:
        e, q, seq = update.event, update.pass_quality, update.event.sequence
        team = self.teams.get(e.team_id or "", "")
        player, other = self._name(e.player_id), self._name(e.receiver_id or e.opponent_id)
        if e.event_type is EventType.PASS and e.outcome is Outcome.SUCCESS and q is not None:
            if q.length_m >= LONG_PASS_M:
                return _pick((f"{player} switches play with a {q.length_m:.0f} m pass to {other}.",
                              f"Big diagonal from {player}, and {other} brings it down."), seq)
            if q.final_third_entry:
                return _pick((f"{player} slides it forward to {other} in the final third.",
                              f"{team} probe: {player} finds {other} near the box."), seq)
        if e.event_type is EventType.CARRY and (e.length_m or 0.0) >= LONG_CARRY_M:
            return _pick((f"{player} drives forward with the ball.", f"{player} carries it up the pitch for {team}."), seq)
        if e.event_type is EventType.TACKLE:
            return _pick((f"{player} wins it back with a firm tackle on {other}.", f"Good challenge from {player}."), seq)
        if e.event_type is EventType.INTERCEPTION:
            return _pick((f"{player} reads it and intercepts.", f"{player} steps in to cut that out."), seq)
        if e.event_type is EventType.PRESSURE and e.start and e.start.x >= HIGH_PRESS_X_M:
            return f"{team} press high, and {other} is hurried on the ball."
        return None

    def _spell(self, update: AnalysisUpdate) -> str | None:
        e = update.event
        if e.event_type is not EventType.PASS or e.outcome is not Outcome.SUCCESS:
            return None
        possession, count = self.spell
        count = count + 1 if possession == e.possession_id else 1
        self.spell = (e.possession_id, count)
        if count == SPELL_PASSES:
            return f"{self.teams.get(e.team_id or '', '')} keep it well: {SPELL_PASSES} passes in this move."
        return None

    def observe(self, update: AnalysisUpdate) -> CommentaryLine | None:
        """Return a commentary line for this update, or None when it is not worth a line yet."""
        e = update.event
        if e.event_type is EventType.PERIOD_START and e.period > 1:
            self.restart = "second_half"
        if e.event_type is EventType.GOAL:
            self.restart = "goal"
        if e.event_type is EventType.KICK_OFF:
            team = self.teams.get(e.team_id or "", "")
            text = {"first_half": f"Kick-off at {self.metadata.venue}! {team} get us under way.",
                    "second_half": f"We're back under way for the second half, {team} kicking off.",
                    "goal": f"{team} restart after the goal."}[self.restart]
            return self._line(update, text, "kick_off", paced=False)
        if e.event_type is EventType.PERIOD_END:
            stage = "Half-time" if e.period == 1 else "Full-time"
            score = f"{self.metadata.home.name} {e.score_home}-{e.score_away} {self.metadata.away.name}"
            return self._line(update, f"{stage}: {score}.", "period_end", paced=False)
        spell_text = self._spell(update)
        text = spell_text or self._flow(update)
        return self._line(update, text, "play") if text else None
