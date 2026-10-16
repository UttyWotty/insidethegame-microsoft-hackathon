"""Pure assembly of an automated highlights reel from key moments, stored tracking frames, and commentary.

At half-time or full-time the reel takes every goal plus the most important other moments up to MAX_CLIPS, in
match order, and cuts each one a few seconds either side of the moment from the frames recorded during the
replay (instant replays use a shorter window around a single action). Each clip carries the best available narration: the viewer's own commentary, the produced commentary,
or a grounded label built from the moment's facts. Tactical Scout flags are never clipped: they have no single action to replay.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from insidegame.agents.recap_context import MIN_TURNING_POINT_IMPORTANCE, RecapStage, moment_actor
from insidegame.analytics.moments import KeyMoment, MomentKind, moment_intensity
from insidegame.tracking.model import Frame

MAX_CLIPS: int = 6
LEAD_S: float = 10.0
TAIL_S: float = 4.0
REPLAY_LEAD_S: float = 6.0
REPLAY_TAIL_S: float = 2.5
FIRST_HALF: int = 1
DEFAULT_LANGUAGE: str = "en"
KIND_TITLES: dict[MomentKind, str] = {
    MomentKind.GOAL: "Goal", MomentKind.BIG_CHANCE_MISSED: "Big chance", MomentKind.GREAT_SAVE: "Great save",
    MomentKind.SPEED_THRESHOLD: "Thunderous strike", MomentKind.DISTANCE_THRESHOLD: "Long-range play",
    MomentKind.DIFFICULT_PASS: "Defence-splitting pass", MomentKind.MOMENTUM_SWING: "Momentum swing",
    MomentKind.CHAOS_SPELL: "Chaotic spell", MomentKind.MILESTONE: "Milestone",
    MomentKind.TACTICAL_PATTERN: "Tactical Scout flag", MomentKind.THREAT_CREATED: "Line-breaking pass",
}
UNCLIPPED_KINDS: frozenset[MomentKind] = frozenset({MomentKind.TACTICAL_PATTERN})


@dataclass(frozen=True)
class FrameRecord:
    """One tracking frame stored during the replay, in the absolute home frame."""

    period: int
    match_second: float
    event_type: str
    player_id: str | None
    ball: tuple[float, float]
    positions: Frame

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        return {"period": self.period, "match_second": self.match_second, "event_type": self.event_type,
                "player_id": self.player_id, "ball": list(self.ball),
                "positions": [list(p) for p in self.positions]}


@dataclass(frozen=True)
class Narration:
    """A spoken and captioned line for a clip, with its language."""

    text: str
    language: str = DEFAULT_LANGUAGE


@dataclass(frozen=True)
class Clip:
    """One replayed moment of the reel."""

    moment: KeyMoment
    title: str
    narration: Narration
    frames: list[FrameRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
        m = self.moment
        return {"moment_id": m.moment_id, "kind": m.kind.value, "minute": m.minute_label, "period": m.period,
                "match_second": m.match_second, "title": self.title, "actor": moment_actor(dict(m.facts)),
                "commentary": self.narration.text,
                "language": self.narration.language, "intensity": moment_intensity(m.kind).value,
                "frames": [f.to_dict() for f in self.frames]}


def select_moments(moments: Sequence[KeyMoment], stage: RecapStage) -> list[KeyMoment]:
    """Goals plus the most important other turning points, up to MAX_CLIPS, in match order, never Scout flags.

    A half-time reel covers the first half only; a full-time reel covers the whole match.
    """
    pool = [m for m in moments if (stage is RecapStage.FULL_TIME or m.period == FIRST_HALF)
            and m.kind not in UNCLIPPED_KINDS]
    goals = [m for m in pool if m.kind is MomentKind.GOAL]
    others = sorted((m for m in pool if m.kind is not MomentKind.GOAL and m.importance >= MIN_TURNING_POINT_IMPORTANCE),
                    key=lambda m: m.importance, reverse=True)
    chosen = (sorted(goals, key=lambda m: m.importance, reverse=True) + others)[:MAX_CLIPS]
    return sorted(chosen, key=lambda m: (m.period, m.match_second))


def clip_frames(frames: Sequence[FrameRecord], moment: KeyMoment) -> list[FrameRecord]:
    """Frames from LEAD_S before the moment to TAIL_S after it, in the moment's period."""
    start, end = moment.match_second - LEAD_S, moment.match_second + TAIL_S
    return [f for f in frames if f.period == moment.period and start <= f.match_second <= end]


def replay_frames(frames: Sequence[FrameRecord], period: int, at: float) -> list[FrameRecord]:
    """Frames for an instant replay: REPLAY_LEAD_S before the action to REPLAY_TAIL_S after, in its period."""
    start, end = at - REPLAY_LEAD_S, at + REPLAY_TAIL_S
    return [f for f in frames if f.period == period and start <= f.match_second <= end]


def fallback_narration(moment: KeyMoment) -> Narration:
    """A grounded caption from the moment's facts when no commentary was produced."""
    actor = moment_actor(dict(moment.facts))
    title = KIND_TITLES.get(moment.kind, moment.kind.value.replace("_", " ").capitalize())
    return Narration(f"{moment.minute_label} {title}" + (f": {actor}." if actor else "."))


def build_reel(moments: Sequence[KeyMoment], stage: RecapStage, frames: Sequence[FrameRecord],
               narrations: Mapping[str, Narration]) -> list[Clip]:
    """Assemble the reel; narrations maps moment ids to the best line available, falling back to the facts."""
    clips = []
    for moment in select_moments(moments, stage):
        cut = clip_frames(frames, moment)
        if not cut:
            continue
        title = KIND_TITLES.get(moment.kind, moment.kind.value)
        clips.append(Clip(moment, title, narrations.get(moment.moment_id) or fallback_narration(moment), cut))
    return clips
