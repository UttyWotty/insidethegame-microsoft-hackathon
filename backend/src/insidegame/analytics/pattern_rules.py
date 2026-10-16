"""Pure tactical pattern rules evaluated over a rolling window of final-third entries and ball wins.

Each rule looks at one team's samples and returns a TacticalPattern when its named thresholds are met, else None.
The rules know nothing about time or cooldowns; the stateful PatternMiner in patterns.py owns the windows.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from insidegame.core.zones import Channel, Third

PATTERN_WINDOW_S: float = 900.0
FINAL_THIRD_X_M: float = 70.0
CHANNEL_OVERLOAD_MIN_COUNT: int = 7
CHANNEL_OVERLOAD_MIN_SHARE: float = 0.60
FLANK_EXPOSED_MIN_SUCCESSES: int = 6
FLANK_EXPOSED_MIN_RATE: float = 0.85
TURNOVER_ZONE_MIN_WINS: int = 5
WIDE_CHANNELS: tuple[Channel, ...] = (Channel.LEFT, Channel.RIGHT)
CHANNEL_ORDER: tuple[Channel, ...] = (Channel.LEFT, Channel.CENTRE, Channel.RIGHT)
THIRD_ORDER: tuple[Third, ...] = (Third.DEFENSIVE, Third.MIDDLE, Third.FINAL)
EMPTY_SHARE: float = 0.0


class PatternKind(StrEnum):
    """The tactical pattern a rule recognised."""

    FLANK_EXPOSED = "flank_exposed"
    CHANNEL_OVERLOAD = "channel_overload"
    TURNOVER_ZONE = "turnover_zone"


PATTERN_PRIORITY: tuple[PatternKind, ...] = (
    PatternKind.FLANK_EXPOSED, PatternKind.CHANNEL_OVERLOAD, PatternKind.TURNOVER_ZONE,
)


@dataclass(frozen=True)
class EntrySample:
    """One attempted entry into the final third, with the channel (in the attacker's frame) it was aimed at."""

    match_second: float
    team_id: str
    channel: Channel
    success: bool


@dataclass(frozen=True)
class WinSample:
    """One ball win outside the winner's defensive third, in the winner's frame."""

    match_second: float
    team_id: str
    third: Third
    channel: Channel


@dataclass(frozen=True)
class TacticalPattern:
    """A recognised pattern: team_id benefits from it, opponent_id suffers it; zone is in team_id's frame."""

    kind: PatternKind
    team_id: str
    opponent_id: str
    channel: Channel
    third: Third
    count: int
    total: int
    window_s: float

    @property
    def key(self) -> tuple[PatternKind, str, Channel, Third]:
        """Identity used for cooldowns: the same kind, team, and zone."""
        return (self.kind, self.team_id, self.channel, self.third)

    @property
    def share(self) -> float:
        """count / total, or 0.0 when total is 0."""
        return self.count / self.total if self.total else EMPTY_SHARE


def channel_overload(entries: Sequence[EntrySample], team_id: str, opponent_id: str) -> TacticalPattern | None:
    """A team sends at least the minimum count and share of its successful final-third entries down one channel."""
    channels = [e.channel for e in entries if e.team_id == team_id and e.success]
    if not channels:
        return None
    counts = Counter(channels)
    channel = max(CHANNEL_ORDER, key=lambda c: (counts[c], -CHANNEL_ORDER.index(c)))
    count, total = counts[channel], len(channels)
    if count < CHANNEL_OVERLOAD_MIN_COUNT or count / total < CHANNEL_OVERLOAD_MIN_SHARE:
        return None
    return TacticalPattern(PatternKind.CHANNEL_OVERLOAD, team_id, opponent_id, channel, Third.FINAL, count, total,
                           PATTERN_WINDOW_S)


def flank_exposed(entries: Sequence[EntrySample], team_id: str, opponent_id: str) -> TacticalPattern | None:
    """A team completes nearly every entry attempted down one wide channel, at least the minimum number of times."""
    best: TacticalPattern | None = None
    for channel in WIDE_CHANNELS:
        attempts = [e.success for e in entries if e.team_id == team_id and e.channel is channel]
        successes = sum(attempts)
        if successes < FLANK_EXPOSED_MIN_SUCCESSES or successes / len(attempts) < FLANK_EXPOSED_MIN_RATE:
            continue
        found = TacticalPattern(PatternKind.FLANK_EXPOSED, team_id, opponent_id, channel, Third.FINAL, successes,
                                len(attempts), PATTERN_WINDOW_S)
        if best is None or (found.share, found.count) > (best.share, best.count):
            best = found
    return best


def turnover_zone(wins: Sequence[WinSample], team_id: str, opponent_id: str) -> TacticalPattern | None:
    """A team keeps winning the ball in one zone outside its own defensive third."""
    zones = [(w.third, w.channel) for w in wins if w.team_id == team_id and w.third is not Third.DEFENSIVE]
    if not zones:
        return None
    counts = Counter(zones)
    third, channel = max(counts, key=lambda z: (counts[z], THIRD_ORDER.index(z[0]), -CHANNEL_ORDER.index(z[1])))
    count = counts[(third, channel)]
    if count < TURNOVER_ZONE_MIN_WINS:
        return None
    return TacticalPattern(PatternKind.TURNOVER_ZONE, team_id, opponent_id, channel, third, count, len(zones),
                           PATTERN_WINDOW_S)
