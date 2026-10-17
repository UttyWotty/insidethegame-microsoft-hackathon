"""Pure demo-story scorer: does a simulated match tell the Tactical Scout story the demo video needs, and how well.

score_story applies eight hard rules (flag count, a flagged go-ahead home goal down a flank, a later dropped shape
shift with falling control, a big save, a passing build-up, and an arc-goal auto replay that plays under the
frontend's replay queue rules, which played_replays mirrors).
It returns a DemoStory with the facts the demo script quotes and a preference score, or None when any rule fails.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.analytics.xg import expected_goals
from insidegame.core.clock import minute_label
from insidegame.core.constants import SECONDS_PER_MINUTE
from insidegame.core.zones import Channel, opposite_flank
from insidegame.domain.enums import EventType, Outcome, ShotResult
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchMetadata

DEMO_SPEED: float = 30.0
REPLAY_DELAY_S: float = 3.5
REPLAY_ROLL_S: float = 17.0
REPLAY_MIN_XG: float = 0.25
# Mirrors frontend/src/lib/replayQueue.ts: replays waiting behind the rolling one, and the most a queued shot may
# trail the live match clock (match seconds) and still be replayed.
REPLAY_QUEUE_MAX: int = 2
REPLAY_MAX_LAG_MATCH_S: float = 600.0
# Mirrors insidegame.live.pacing.HALF_TIME_BREAK_MATCH_S: the live stream's half-time pause, in match seconds.
HALF_TIME_BREAK_MATCH_S: float = 60.0

GO_AHEAD: str = "go_ahead"
DROPPED: str = "dropped"
WENT_AHEAD: str = "went_ahead"
FLANK_CHANNELS: frozenset[str] = frozenset({Channel.LEFT.value, Channel.RIGHT.value})
NO_LIVE_CLOCK: float = float("-inf")

WINNER_POINTS: int = 3
COMEBACK_POINTS: int = 2
LATE_POINTS: int = 2
QUICK_LEAD_POINTS: int = 1
QUICK_LEAD_MINUTES: float = 10.0
EXPLOITED_FLANK_POINTS: int = 1
SAVE_REPLAY_POINTS: int = 1
BUILD_UP_POINTS: int = 1


@dataclass(frozen=True)
class StoryCriteria:
    """Hard-rule thresholds for a demo story.

    Defaults: at most 9 Tactical Scout flags (max_flags = 9); the arc goal comes 3.0 to 12.0 minutes after its flag
    (min_lead_minutes, max_lead_minutes); it is struck from at least 6.0 m (min_shot_distance_m); some goal follows
    at least 2 completed passes (min_build_up_passes = 2); and an arc goal from minute 70 on is late (late_minute).
    """

    max_flags: int = 9
    min_lead_minutes: float = 3.0
    max_lead_minutes: float = 12.0
    min_shot_distance_m: float = 6.0
    min_build_up_passes: int = 2
    late_minute: int = 70


@dataclass(frozen=True)
class DemoStory:
    """The facts of a seed that passes every hard rule, and its preference score."""

    seed: int
    home_goals: int
    away_goals: int
    goal_minutes: tuple[str, ...]
    flag_minute: str
    flag_pattern: str
    flag_channel: str
    flag_summary: str
    arc_minute: str
    arc_scorer: str
    arc_score: str
    arc_xg: float
    arc_distance_m: float
    arc_build_up_passes: int
    lead_minutes: float
    shift_minute: str
    shift_line_before_m: float
    shift_line_after_m: float
    save_minutes: tuple[str, ...]
    save_replay_plays: bool
    flags: int
    winner: bool
    comeback: bool
    late: bool
    exploited_flank: bool
    score: int


@dataclass(frozen=True)
class ReplayCandidate:
    """A shot that earns an auto replay: when the broadcast shows it (stream seconds), its match second, and goal."""

    stream_s: float
    match_second: float
    goal: bool


def stream_times(events: Sequence[tuple[int, float]]) -> list[float]:
    """Stream time, in match seconds of wall clock at speed 1, at which each (period, match second) event is shown.

    Within a period the stream advances with the match clock (never backwards); a period change adds the live
    service's half-time break (HALF_TIME_BREAK_MATCH_S), as insidegame.live.pacing does.
    """
    times: list[float] = []
    previous: tuple[int, float] | None = None
    for period, second in events:
        gap = 0.0 if previous is None else (
            HALF_TIME_BREAK_MATCH_S if period != previous[0] else max(0.0, second - previous[1]))
        times.append((times[-1] if times else 0.0) + gap)
        previous = (period, second)
    return times


def _enqueue(queue: list[int], index: int, goals: Sequence[bool]) -> list[int]:
    """Queue cap: a goal replaces the oldest non-goal when full, a non-goal arriving at a full queue is dropped."""
    if len(queue) < REPLAY_QUEUE_MAX:
        return [*queue, index]
    oldest = next((i for i, queued in enumerate(queue) if not goals[queued]), None)
    if not goals[index] or oldest is None:
        return queue
    return [*queue[:oldest], *queue[oldest + 1:], index]


def played_replays(shots: Sequence[ReplayCandidate], clock: Sequence[tuple[float, float]], speed: float,
                   delay_s: float, roll_s: float) -> list[bool]:
    """Whether each shot's auto replay plays, in order, under the frontend's queue rules (lib/replayQueue.ts).

    A replay is due delay_s * speed stream seconds after its shot and rolls for roll_s * speed. One due while
    another rolls joins a queue of REPLAY_QUEUE_MAX (goal priority); when a replay ends, queued shots more than
    REPLAY_MAX_LAG_MATCH_S behind the live match second are dropped. clock lists (stream seconds, match second) for
    every event in order, so the live match second at any stream time is that of the latest event shown.
    The frontend also holds due replays in the queue while a recap dialog is open; this model has no recap dialogs,
    so it assumes the viewer closes each recap promptly (the half-time recap closes itself after 15 s), as the live
    demo does.
    """
    stamps = [t for t, _ in clock]
    goals = [shot.goal for shot in shots]
    played = [False] * len(shots)
    queue: list[int] = []
    rolling_until: float | None = None

    def live_second(at: float) -> float:
        found = bisect_right(stamps, at)
        return clock[found - 1][1] if found else NO_LIVE_CLOCK

    def advance(to: float) -> None:
        nonlocal queue, rolling_until
        while rolling_until is not None and rolling_until <= to:
            live = live_second(rolling_until)
            queue = [i for i in queue if live - shots[i].match_second <= REPLAY_MAX_LAG_MATCH_S]
            if not queue:
                rolling_until = None
                break
            played[queue.pop(0)] = True
            rolling_until += roll_s * speed

    for index, shot in enumerate(shots):
        due = shot.stream_s + delay_s * speed
        advance(due)
        if rolling_until is None:
            played[index], rolling_until = True, due + roll_s * speed
        else:
            queue = _enqueue(queue, index, goals)
    advance(float("inf"))
    return played


def build_up_passes(events: Sequence[MatchEvent], shot: MatchEvent) -> int:
    """Completed passes by the shooting team in the shot's possession before the shot."""
    return sum(1 for e in events if e.possession_id == shot.possession_id and e.team_id == shot.team_id
               and e.event_type is EventType.PASS and e.outcome is Outcome.SUCCESS and e.sequence < shot.sequence)


def _shot_xg(event: MatchEvent) -> float:
    return expected_goals(event.start, event.under_pressure) if event.start is not None else 0.0


def _arc_goal(moments: Sequence[KeyMoment]) -> KeyMoment | None:
    return next((m for m in moments if m.kind is MomentKind.GOAL and "flagged_moment_id" in m.facts
                 and m.facts["game_state_change"] == GO_AHEAD), None)


def _drop_shift(moments: Sequence[KeyMoment]) -> KeyMoment | None:
    return next((m for m in moments if m.kind is MomentKind.SHAPE_SHIFT and m.facts["direction"] == DROPPED
                 and float(m.facts["goal_difference"]) > 0), None)


def _shift_ok(shift: KeyMoment | None, arc: KeyMoment, home_id: str) -> bool:
    return (shift is not None and shift.team_id == home_id and shift.facts["trigger"] == WENT_AHEAD
            and shift.match_second > arc.match_second
            and float(shift.facts["control_after_pct"]) < float(shift.facts["control_before_pct"]))


def _replay_plays(events: Sequence[MatchEvent]) -> dict[str, bool]:
    """Auto-replay outcome at DEMO_SPEED for every goal and every shot of at least REPLAY_MIN_XG, by event id."""
    times = stream_times([(e.period, e.match_second) for e in events])
    eligible = [(e, t) for e, t in zip(events, times, strict=True) if e.event_type is EventType.SHOT
                and (e.shot_result is ShotResult.GOAL or _shot_xg(e) >= REPLAY_MIN_XG)]
    shots = [ReplayCandidate(t, e.match_second, e.shot_result is ShotResult.GOAL) for e, t in eligible]
    clock = [(t, e.match_second) for e, t in zip(events, times, strict=True)]
    plays = played_replays(shots, clock, DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S)
    return {e.event_id: p for (e, _), p in zip(eligible, plays, strict=True)}


def _lead_minutes(arc: KeyMoment, flag: KeyMoment) -> float:
    return (arc.match_second - flag.match_second) / SECONDS_PER_MINUTE


def _arc_ok(arc: KeyMoment | None, flag: KeyMoment | None, home_id: str, criteria: StoryCriteria) -> bool:
    """Rules 2 to 4: a home flagged go-ahead goal, from a home flank flag, in the lead window, not a tap-in."""
    if arc is None or flag is None or arc.team_id != home_id or flag.team_id != home_id:
        return False
    if str(flag.facts["channel"]) not in FLANK_CHANNELS:
        return False
    lead = _lead_minutes(arc, flag)
    return (criteria.min_lead_minutes <= lead <= criteria.max_lead_minutes
            and float(arc.facts["distance_m"]) >= criteria.min_shot_distance_m)


def _preferences(arc: KeyMoment, goals: Sequence[KeyMoment]) -> tuple[bool, bool]:
    """Whether the arc goal is never cancelled (winner) and whether home trailed before it (comeback)."""
    later, earlier = ([g for g in goals if g.match_second > arc.match_second],
                      [g for g in goals if g.match_second < arc.match_second])
    winner = all(int(g.facts["score_home"]) > int(g.facts["score_away"]) for g in later)
    comeback = any(int(g.facts["score_away"]) > int(g.facts["score_home"]) for g in earlier)
    return winner, comeback


def _score(winner: bool, comeback: bool, late: bool, lead: float, exploited: bool, save_plays: bool,
           arc_passes: int, criteria: StoryCriteria) -> int:
    return (WINNER_POINTS * winner + COMEBACK_POINTS * comeback + LATE_POINTS * late
            + QUICK_LEAD_POINTS * (lead <= QUICK_LEAD_MINUTES) + EXPLOITED_FLANK_POINTS * exploited
            + SAVE_REPLAY_POINTS * save_plays + BUILD_UP_POINTS * (arc_passes >= criteria.min_build_up_passes))


def score_story(seed: int, metadata: MatchMetadata, events: Sequence[MatchEvent], moments: Sequence[KeyMoment],
                criteria: StoryCriteria) -> DemoStory | None:
    """Return the seed's DemoStory when all eight hard rules hold, otherwise None."""
    home_id = metadata.home.team_id
    by_moment = {m.moment_id: m for m in moments}
    by_event = {e.event_id: e for e in events}
    flags = sum(m.kind is MomentKind.TACTICAL_PATTERN for m in moments)
    arc = _arc_goal(moments)
    flag = by_moment.get(str(arc.facts["flagged_moment_id"])) if arc is not None else None
    if flags > criteria.max_flags or not _arc_ok(arc, flag, home_id, criteria):
        return None
    shift = _drop_shift(moments)
    if not _shift_ok(shift, arc, home_id):
        return None
    plays = _replay_plays(events)
    saves = [e for e in events if e.event_type is EventType.SHOT and e.shot_result is ShotResult.SAVED
             and _shot_xg(e) >= REPLAY_MIN_XG]
    goals = [m for m in moments if m.kind is MomentKind.GOAL]
    passes = {g.moment_id: build_up_passes(events, by_event[g.event_ids[0]]) for g in goals}
    if not saves or max(passes.values()) < criteria.min_build_up_passes or not plays.get(arc.event_ids[0], False):
        return None
    return _story(seed, metadata, events, arc, flag, shift, goals, saves, plays, passes, flags, criteria)


def _story(seed: int, metadata: MatchMetadata, events: Sequence[MatchEvent], arc: KeyMoment, flag: KeyMoment,
           shift: KeyMoment, goals: Sequence[KeyMoment], saves: Sequence[MatchEvent], plays: dict[str, bool],
           passes: dict[str, int], flags: int, criteria: StoryCriteria) -> DemoStory:
    winner, comeback = _preferences(arc, goals)
    late = arc.minute >= criteria.late_minute
    lead = _lead_minutes(arc, flag)
    exploited = flag.facts["channel"] == opposite_flank(metadata.away.style.weak_flank).value
    save_plays = any(plays.get(e.event_id, False) for e in saves)
    arc_passes = passes[arc.moment_id]
    return DemoStory(
        seed=seed, home_goals=events[-1].score_home, away_goals=events[-1].score_away,
        goal_minutes=tuple(g.minute_label for g in goals),
        flag_minute=flag.minute_label, flag_pattern=str(flag.facts["pattern"]), flag_channel=str(flag.facts["channel"]),
        flag_summary=str(flag.facts["summary"]),
        arc_minute=arc.minute_label, arc_scorer=str(arc.facts["scorer"]),
        arc_score=f"{arc.facts['score_home']}-{arc.facts['score_away']}", arc_xg=float(arc.facts["xg"]),
        arc_distance_m=float(arc.facts["distance_m"]), arc_build_up_passes=arc_passes, lead_minutes=round(lead, 1),
        shift_minute=shift.minute_label, shift_line_before_m=float(shift.facts["line_before_m"]),
        shift_line_after_m=float(shift.facts["line_after_m"]),
        save_minutes=tuple(minute_label(e.match_second, e.period) for e in saves), save_replay_plays=save_plays,
        flags=flags, winner=winner, comeback=comeback, late=late, exploited_flank=exploited,
        score=_score(winner, comeback, late, lead, exploited, save_plays, arc_passes, criteria))
