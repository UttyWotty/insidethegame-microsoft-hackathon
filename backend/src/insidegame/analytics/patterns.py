"""Stateful, deterministic tactical pattern miner over a rolling window of the event stream.

PatternMiner collects final-third entries and ball wins, applies the pure rules with a global gap and per-pattern
cooldowns, and tracks each possession's attack channel. payoff links a goal or a shot back to the most recent
earlier flag it fulfils, so the broadcast can say a pattern was flagged before it was punished.
"""

from collections import deque
from dataclasses import dataclass, field

from insidegame.analytics.moments import FactValue
from insidegame.analytics.pattern_rules import (
    FINAL_THIRD_X_M,
    PATTERN_PRIORITY,
    PATTERN_WINDOW_S,
    EntrySample,
    PatternKind,
    TacticalPattern,
    WinSample,
    channel_overload,
    flank_exposed,
    turnover_zone,
)
from insidegame.core.zones import Channel, Third, channel_of, third_of
from insidegame.domain.enums import EventType, Outcome
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

PATTERN_GAP_S: float = 600.0
PATTERN_KEY_COOLDOWN_S: float = 900.0
PAYOFF_WINDOW_S: float = 900.0
NEVER_S: float = float("-inf")
ENTRY_TYPES: frozenset[EventType] = frozenset({EventType.PASS, EventType.CARRY})
PAYOFF_TYPES: frozenset[EventType] = frozenset({EventType.GOAL, EventType.SHOT})
CHANNEL_KINDS: frozenset[PatternKind] = frozenset({PatternKind.FLANK_EXPOSED, PatternKind.CHANNEL_OVERLOAD})


@dataclass(frozen=True)
class FlagRecord:
    """A pattern that was raised as a key moment, remembered for payoff links."""

    pattern: TacticalPattern
    moment_id: str
    period: int
    match_second: float
    minute_label: str
    summary: str


@dataclass(frozen=True)
class PayoffLink:
    """A goal or chance that fulfilled an earlier flag."""

    flag: FlagRecord

    def facts(self) -> dict[str, FactValue]:
        """Facts added to the linked goal or big chance moment."""
        return {"flagged_minute": self.flag.minute_label, "flagged_moment_id": self.flag.moment_id,
                "flagged_pattern": self.flag.pattern.kind.value, "flagged_summary": self.flag.summary}


@dataclass
class _Possession:
    team_id: str
    first_second: float
    start_third: Third
    start_channel: Channel
    began_with_win: bool
    entry_channel: Channel | None = None

    def attack_channel(self) -> Channel | None:
        """Last successful final-third entry, else the start channel when it began in the final third."""
        if self.entry_channel is not None:
            return self.entry_channel
        return self.start_channel if self.start_third is Third.FINAL else None


@dataclass
class PatternMiner:
    """Mines tactical patterns from events as they arrive; at most one new pattern per event."""

    metadata: MatchMetadata
    entries: deque[EntrySample] = field(default_factory=deque)
    wins: deque[WinSample] = field(default_factory=deque)
    flags: list[FlagRecord] = field(default_factory=list)
    possessions: dict[int, _Possession] = field(default_factory=dict)
    last_flag_s: float = NEVER_S
    last_key_s: dict[tuple[PatternKind, str, Channel, Third], float] = field(default_factory=dict)

    def observe(self, event: MatchEvent) -> TacticalPattern | None:
        """Fold one event into the windows and return a newly recognised pattern, if any."""
        if event.event_type is EventType.PERIOD_START:
            self._reset()
            return None
        if event.team_id is None or event.start is None:
            return None
        now = event.match_second
        self._expire(now)
        self._track(event)
        if now - self.last_flag_s < PATTERN_GAP_S:
            return None
        pattern = self._best_candidate(now)
        if pattern is not None:
            self.last_flag_s = now
            self.last_key_s[pattern.key] = now
        return pattern

    def record_flag(self, flag: FlagRecord) -> None:
        """Remember a raised flag so later goals and chances can link to it."""
        self.flags.append(flag)

    def payoff(self, event: MatchEvent) -> PayoffLink | None:
        """The most recent earlier flag this goal or shot fulfils, or None."""
        if event.event_type not in PAYOFF_TYPES or event.team_id is None:
            return None
        possession = self.possessions.get(event.possession_id)
        if possession is None or possession.team_id != event.team_id:
            return None
        linked = [f for f in self.flags if self._links(f, event, possession)]
        return PayoffLink(linked[-1]) if linked else None

    def _reset(self) -> None:
        self.entries.clear()
        self.wins.clear()
        self.possessions.clear()
        self.last_key_s.clear()
        self.last_flag_s = NEVER_S

    def _expire(self, now: float) -> None:
        for window in (self.entries, self.wins):
            while window and now - window[0].match_second > PATTERN_WINDOW_S:
                window.popleft()

    def _track(self, event: MatchEvent) -> None:
        team_id, start = event.team_id, event.start
        if team_id is None or start is None:
            return
        possession = self.possessions.get(event.possession_id)
        if possession is None:
            is_win = event.event_type is EventType.POSSESSION_CHANGE
            possession = _Possession(team_id, event.match_second, third_of(start.x), channel_of(start.y), is_win)
            self.possessions[event.possession_id] = possession
            if is_win and possession.start_third is not Third.DEFENSIVE:
                self.wins.append(WinSample(event.match_second, team_id, possession.start_third,
                                           possession.start_channel))
        end = event.end
        if event.event_type in ENTRY_TYPES and end is not None and start.x < FINAL_THIRD_X_M <= end.x:
            success = event.outcome is Outcome.SUCCESS
            self.entries.append(EntrySample(event.match_second, team_id, channel_of(end.y), success))
            if success and possession.team_id == team_id:
                possession.entry_channel = channel_of(end.y)

    def _best_candidate(self, now: float) -> TacticalPattern | None:
        home, away = self.metadata.home.team_id, self.metadata.away.team_id
        candidates: dict[PatternKind, list[TacticalPattern | None]] = {
            PatternKind.FLANK_EXPOSED: [flank_exposed(self.entries, home, away), flank_exposed(self.entries, away, home)],
            PatternKind.CHANNEL_OVERLOAD: [channel_overload(self.entries, home, away),
                                           channel_overload(self.entries, away, home)],
            PatternKind.TURNOVER_ZONE: [turnover_zone(self.wins, home, away), turnover_zone(self.wins, away, home)],
        }
        for kind in PATTERN_PRIORITY:
            for pattern in candidates[kind]:
                if pattern is not None and now - self.last_key_s.get(pattern.key, NEVER_S) >= PATTERN_KEY_COOLDOWN_S:
                    return pattern
        return None

    @staticmethod
    def _links(flag: FlagRecord, event: MatchEvent, possession: _Possession) -> bool:
        pattern = flag.pattern
        if (flag.period != event.period or pattern.team_id != event.team_id
                or flag.match_second >= possession.first_second
                or event.match_second - flag.match_second > PAYOFF_WINDOW_S):
            return False
        if pattern.kind in CHANNEL_KINDS:
            return possession.attack_channel() is pattern.channel
        return (possession.began_with_win and possession.start_third is pattern.third
                and possession.start_channel is pattern.channel)
