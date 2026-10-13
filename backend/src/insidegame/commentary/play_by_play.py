"""Deterministic play-by-play commentary generated from interpreted events.

Lines cover kick-offs, period ends, attacks into the final third, long passes, dribbles, tackles, interceptions,
high pressing, and sustained possession, paced by a minimum gap so the feed stays readable. Goals and close calls
always get a line, written and flagged with raised or peak intensity so the voice can lift with the moment.
In the first lull after kick-off a short scene-setting line introduces both sides' styles, so it never talks over
the opening play, and later quiet spells get everyday possession lines so the commentator is never silent for long.
"""

from collections import Counter, deque
from dataclasses import dataclass, field

from insidegame.analytics.analyzer import AnalysisUpdate
from insidegame.analytics.detectors import BIG_CHANCE_XG
from insidegame.core.clock import minute_label
from insidegame.domain.enums import EventType, Intensity, Outcome, ShotResult
from insidegame.domain.match import MatchMetadata

MIN_GAP_S: float = 50.0
WALL_GAP_S: float = 5.0
MIN_MATCH_GAP_S: float = 15.0
MAX_MATCH_GAP_S: float = 300.0
LONG_PASS_M: float = 35.0
LONG_CARRY_M: float = 12.0
HIGH_PRESS_X_M: float = 70.0
ATTACKING_HALF_X_M: float = 52.5
SPELL_PASSES: int = 8
RECENT_LINES: int = 30
FILLER_GAP_FACTOR: float = 1.3
STYLE_PHRASES: dict[str, str] = {
    "possession": "like to keep the ball", "direct": "like to go direct", "high_press": "press high up the pitch",
    "counter": "wait to hit on the counter",
}


@dataclass(frozen=True)
class CommentaryLine:
    """One play-by-play line."""

    line_id: str
    period: int
    match_second: float
    minute: str
    text: str
    kind: str
    intensity: Intensity = Intensity.NORMAL

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return dict(self.__dict__) | {"intensity": self.intensity.value}


def line_gap_for_speed(speed: float) -> float:
    """Match seconds between ordinary lines for a replay speed: about WALL_GAP_S of viewing time per line.

    The gap is bounded to MIN_MATCH_GAP_S..MAX_MATCH_GAP_S, so real-time viewing keeps a natural commentary rhythm
    and very fast replays do not flood the feed; at 10x it equals the default MIN_GAP_S of 50 match seconds.
    """
    return min(max(WALL_GAP_S * speed, MIN_MATCH_GAP_S), MAX_MATCH_GAP_S)


@dataclass
class PlayByPlay:
    """Turns analysis updates into paced commentary lines for one match."""

    metadata: MatchMetadata
    names: dict[str, str] = field(default_factory=dict)
    teams: dict[str, str] = field(default_factory=dict)
    last_line_s: float | None = None
    spell: tuple[int, int] = (-1, 0)
    restart: str = "first_half"
    min_gap_s: float = MIN_GAP_S
    turns: Counter[str] = field(default_factory=Counter)
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=RECENT_LINES))
    last_category: str = ""
    introduced: bool = False

    def __post_init__(self) -> None:
        for team in (self.metadata.home, self.metadata.away):
            self.teams[team.team_id] = team.name
            self.names.update({p.player_id: p.name for p in team.players})

    def _name(self, player_id: str | None) -> str:
        return self.names.get(player_id or "", "")

    def _choose(self, category: str, options: tuple[str, ...], must_air: bool = False) -> str | None:
        """Pick the next wording in rotation that has not aired in the last RECENT_LINES lines.

        Ordinary lines (must_air False, the default) are skipped when they would repeat the previous line's category
        or every wording is recent; must-air lines (goals, close calls, restarts) always return a wording.
        """
        if not must_air and category == self.last_category:
            return None
        start = self.turns[category]
        fresh = [k for k in range(len(options)) if options[(start + k) % len(options)] not in self.recent]
        if not fresh and not must_air:
            return None
        step = fresh[0] if fresh else 0
        text = options[(start + step) % len(options)]
        self.turns[category] = start + step + 1
        self.recent.append(text)
        self.last_category = category
        return text

    def _line(self, update: AnalysisUpdate, text: str, kind: str, paced: bool = True,
              intensity: Intensity = Intensity.NORMAL) -> CommentaryLine | None:
        """Build a line; paced lines (the default) respect min_gap_s, and intensity defaults to NORMAL."""
        event = update.event
        if paced and self.last_line_s is not None and event.match_second - self.last_line_s < self.min_gap_s:
            if self.recent and self.recent[-1] == text:
                self.recent.pop()  # the wording did not air, so it must not count against repeats
            return None
        self.last_line_s = event.match_second
        return CommentaryLine(f"{event.event_id}-pbp", event.period, event.match_second,
                              minute_label(event.match_second, event.period), text, kind, intensity)

    def _goal(self, update: AnalysisUpdate) -> CommentaryLine | None:
        e = update.event
        player, team = self._name(e.player_id), self.teams.get(e.team_id or "", "")
        score = f"{e.score_home}-{e.score_away}"
        text = self._choose("goal", (f"GOAL! {player} scores for {team}! It's {score}!",
                                     f"It's in! {player} finds the net, and it's {score}!",
                                     f"GOAL! What a moment for {player}! {team} make it {score}!",
                                     f"GOAL! {player} buries it! {score}!"), must_air=True)
        return self._line(update, text, "goal", paced=False, intensity=Intensity.PEAK)

    def _close_call(self, update: AnalysisUpdate) -> CommentaryLine | None:
        e = update.event
        if e.shot_result is ShotResult.GOAL or (update.xg or 0.0) < BIG_CHANCE_XG:
            return None
        player = self._name(e.player_id)
        text = {
            ShotResult.SAVED: self._choose("saved", (f"Huge chance for {player}, and it's saved! What a stop!",
                                                     f"{player} goes for it, and the keeper keeps it out!",
                                                     f"Saved! {player} was through, but the keeper stands tall!"),
                                          must_air=True),
            ShotResult.OFF_TARGET: self._choose("wide", (f"Oh, so close! {player} fires wide from a great position!",
                                                        f"{player} has to score there, but it's just wide!",
                                                        f"Inches away! {player} drags it past the post!"),
                                             must_air=True),
            ShotResult.BLOCKED: self._choose("blocked", (
                f"{player} pulls the trigger, and it's blocked at the last moment!",
                f"Blocked! {player} thought that was in!"), must_air=True),
        }.get(e.shot_result or ShotResult.OFF_TARGET)
        return self._line(update, text, "close_call", paced=False, intensity=Intensity.RAISED) if text else None

    def _intro(self, update: AnalysisUpdate) -> CommentaryLine | None:
        """One short scene-setting line in the first lull of the first half, naming both clubs' styles."""
        e = update.event
        if self.introduced or self.last_line_s is None or e.period != 1 or not self._quiet(update):
            return None
        self.introduced = True
        home, away = self.metadata.home, self.metadata.away
        text = (f"{home.name} {STYLE_PHRASES.get(home.style.label, 'have their own ideas')}, "
                f"{away.name} {STYLE_PHRASES.get(away.style.label, 'have their own ideas')}.")
        return self._line(update, text, "intro")

    def _quiet(self, update: AnalysisUpdate) -> bool:
        """True when no line has aired for FILLER_GAP_FACTOR times the gap, so an everyday line is welcome."""
        last = self.last_line_s
        return last is None or update.event.match_second - last >= FILLER_GAP_FACTOR * self.min_gap_s

    def _pass_line(self, update: AnalysisUpdate, player: str, other: str, team: str) -> str | None:
        q = update.pass_quality
        if q is None or update.event.outcome is not Outcome.SUCCESS:
            return None
        if q.length_m >= LONG_PASS_M:
            return self._choose("long_pass", (f"{player} switches play with a {q.length_m:.0f}-metre pass to {other}.",
                                              f"Big diagonal from {player}, and {other} brings it down.",
                                              f"{player} goes long, and {other} controls it beautifully.",
                                              f"Lovely range from {player} to find {other}."))
        if q.final_third_entry:
            return self._choose("final_third", (f"{player} slides it forward to {other} in the final third.",
                                                f"{team} probe: {player} finds {other} near the box.",
                                                f"{player} threads it into {other} on the edge of the area.",
                                                f"{team} work it forward, {player} to {other}."))
        if self._quiet(update):
            return self._choose("possession", (f"{team} keep the ball, {player} to {other}.",
                                               f"{player} plays it into {other}.",
                                               f"Patient build-up from {team}.",
                                               f"{player} looks up and finds {other}.",
                                               f"{team} probing for an opening."))
        return None

    def _flow(self, update: AnalysisUpdate) -> str | None:
        e = update.event
        team = self.teams.get(e.team_id or "", "")
        player, other = self._name(e.player_id), self._name(e.receiver_id or e.opponent_id)
        if e.event_type is EventType.PASS:
            return self._pass_line(update, player, other, team)
        if e.event_type is EventType.CARRY and (e.length_m or 0.0) >= LONG_CARRY_M:
            return self._choose("carry", (f"{player} drives forward with the ball.",
                                          f"{player} carries it up the pitch for {team}.",
                                          f"{player} picks it up and runs at the defence.",
                                          f"Purposeful run from {player}."))
        if e.event_type is EventType.TACKLE:
            return self._choose("tackle", (f"{player} wins it back with a firm tackle on {other}.",
                                           f"Good challenge from {player}.", f"{player} slides in and takes the ball.",
                                           f"Strong from {player}, and {team} have it back."))
        if e.event_type is EventType.INTERCEPTION:
            return self._choose("interception", (f"{player} reads it and intercepts.",
                                                 f"{player} steps in to cut that out.",
                                                 f"Smart anticipation from {player}.",
                                                 f"{player} gets a toe to it.",
                                                 f"Cut out by {player}."))
        if e.event_type is EventType.PRESSURE and e.start and e.start.x >= HIGH_PRESS_X_M:
            return self._choose("press", (f"{team} press high, and {other} is hurried on the ball.",
                                          f"{team} hunt it down, and {other} has no time.",
                                          f"Intense pressure from {team} on {other}."))
        return None

    def _spell(self, update: AnalysisUpdate, due: bool) -> str | None:
        """Count consecutive passes in a move; a line is offered only when the move reaches SPELL_PASSES and is due."""
        e = update.event
        if e.event_type is not EventType.PASS or e.outcome is not Outcome.SUCCESS:
            return None
        possession, count = self.spell
        count = count + 1 if possession == e.possession_id else 1
        self.spell = (e.possession_id, count)
        if count == SPELL_PASSES and due:
            team = self.teams.get(e.team_id or "", "")
            return self._choose("spell", (f"{team} keep it well: {SPELL_PASSES} passes in this move.",
                                          f"Patient from {team}, stringing the passes together.",
                                          f"{team} are enjoying the ball here.",
                                          f"Neat and tidy from {team}, keeping possession."))
        return None

    def observe(self, update: AnalysisUpdate) -> CommentaryLine | None:
        """Return a commentary line for this update, or None when it is not worth a line yet."""
        e = update.event
        if e.event_type is EventType.PERIOD_START and e.period > 1:
            self.restart = "second_half"
        if e.event_type is EventType.GOAL:
            self.restart = "goal"
            return self._goal(update)
        if e.event_type is EventType.SHOT:
            return self._close_call(update)
        intro = self._intro(update)
        if intro is not None:
            return intro
        if e.event_type is EventType.KICK_OFF:
            team = self.teams.get(e.team_id or "", "")
            text = {"first_half": f"Kick-off at {self.metadata.venue}! {team} get us under way.",
                    "second_half": f"We're back under way for the second half, {team} kicking off.",
                    "goal": self._choose("restart", (f"{team} restart after the goal.",
                                                     f"{team} get us going again.",
                                                     f"We're back under way, {team} with the kick-off."),
                                         must_air=True) or ""}[self.restart]
            return self._line(update, text, "kick_off", paced=False)
        if e.event_type is EventType.PERIOD_END:
            stage = "Half-time" if e.period == 1 else "Full-time"
            score = f"{self.metadata.home.name} {e.score_home}-{e.score_away} {self.metadata.away.name}"
            return self._line(update, f"{stage}: {score}.", "period_end", paced=False)
        due = self.last_line_s is None or e.match_second - self.last_line_s >= self.min_gap_s
        text = self._spell(update, due) or (self._flow(update) if due else None)
        return self._line(update, text, "play") if text else None
