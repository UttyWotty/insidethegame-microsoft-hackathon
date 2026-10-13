"""A live match session: replays events in real time and publishes results to subscribers.

Interpretation runs inline so the event feed keeps match pace, while agent workflows and recaps run as background
tasks that publish when ready. Moments wait in order for a limited number of production slots, and non-goal moments
that go stale while waiting are skipped. Cues are routed only to subscribers of the segment they were personalized for.
Every tracking frame is kept so half-time and full-time highlights can be replayed.
"""

import asyncio
import logging
import time
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum

from insidegame.agents.context import MomentContext
from insidegame.agents.personas import ViewerProfile, is_relevant
from insidegame.agents.context import ViewerContext
from insidegame.agents.recap_context import RecapContext, RecapStage, build_recap_context
from insidegame.agents.recap_takes import template_take
from insidegame.agents.schemas import MatchRecap, RecapTake
from insidegame.agents.runner import OutputSource
from insidegame.agents.templates import recap_template
from insidegame.commentary.play_by_play import PlayByPlay, line_gap_for_speed
from insidegame.core.exceptions import HighlightsNotReadyError, SessionLimitError
from insidegame.domain.enums import Intensity
from insidegame.domain.events import MatchEvent
from insidegame.domain.match import MatchResult
from insidegame.highlights.reel import FrameRecord, build_reel
from insidegame.live.highlight_lines import clip_narrations
from insidegame.live.pacing import replay_delay_s
from insidegame.live.studio_view import StudioWindow, studio_payload
from insidegame.live.producer import AirStatus, ProducerDesk
from insidegame.live.spoken_lines import find_spoken_line
from insidegame.orchestration.cues import MomentBroadcast
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.producer import is_stale
from insidegame.orchestration.service import MatchIntelligenceService, degraded_broadcast
from insidegame.orchestration.trace import AgentTrace
from insidegame.tracking.model import LOOKAHEAD_EVENTS, Frame

logger = logging.getLogger(__name__)

QUEUE_MAX: int = 2000
CUE_HISTORY: int = 20
SNAPSHOT_EVERY_EVENTS: int = 25
BACKFILL_MOMENTS: int = 2
MAX_SEGMENTS: int = 10
COMMENTARY_HISTORY: int = 40
MOMENT_HISTORY: int = 30
DEFAULT_PARALLEL_MOMENTS: int = 2
BALL_DECIMALS: int = 1
TRACE_HISTORY: int = 12

Sleeper = Callable[[float], Awaitable[None]]


class MessageType(StrEnum):
    """Kinds of messages streamed to clients."""

    MATCH = "match"
    EVENT = "event"
    SNAPSHOT = "snapshot"
    CUE = "cue"
    COMMENTARY = "commentary"
    RECAP = "recap"
    END = "end"


class SessionStatus(StrEnum):
    """Lifecycle of a session."""

    PENDING = "pending"
    LIVE = "live"
    FINISHED = "finished"


@dataclass(frozen=True)
class LiveMessage:
    """One streamed message; segment_id None means every subscriber receives it."""

    type: MessageType
    data: dict[str, object]
    segment_id: str | None = None


@dataclass(eq=False)
class Subscriber:
    """A connected client and its message queue."""

    segment_id: str
    queue: asyncio.Queue[LiveMessage] = field(default_factory=lambda: asyncio.Queue(QUEUE_MAX))


@contextmanager
def _counting(counter: Counter[str], key: str) -> Iterator[None]:
    """Count key in counter for the duration of the block, removing it when the count returns to zero."""
    counter[key] += 1
    try:
        yield
    finally:
        counter[key] -= 1
        if not counter[key]:
            del counter[key]


def _take_fields(viewer: ViewerContext, take: RecapTake, source: OutputSource) -> dict[str, object]:
    return {"persona": viewer.viewer.persona.value, "take": take.model_dump(mode="json"), "take_source": source.value}


class MatchSession:
    """Owns one replayed match, its pipeline, and its subscribers."""

    def __init__(self, session_id: str, result: MatchResult, service: MatchIntelligenceService, speed: float,
                 sleep: Sleeper = asyncio.sleep, parallel_moments: int = DEFAULT_PARALLEL_MOMENTS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        """Create a session.

        sleep defaults to asyncio.sleep and is injectable for tests; parallel_moments (default
        DEFAULT_PARALLEL_MOMENTS = 2) caps how many moments run their agent workflows at once; clock (default
        time.monotonic) times the live agent traces.
        """
        self.session_id, self.result, self.service, self.speed, self.sleep = session_id, result, service, speed, sleep
        self.status = SessionStatus.PENDING
        self.subscribers: set[Subscriber] = set()
        self.cue_history: dict[str, deque[dict[str, object]]] = {}
        self.recaps: list[dict[str, object]] = []
        self.recap_sources: list[tuple[RecapContext, MatchRecap]] = []
        self.tasks: set[asyncio.Task[None]] = set()
        self.recent_moments: deque[MomentContext] = deque(maxlen=MOMENT_HISTORY)
        self.play_by_play = PlayByPlay(result.metadata, min_gap_s=line_gap_for_speed(speed))
        self.desk = ProducerDesk()
        self.in_production: Counter[str] = Counter()
        self.queued: Counter[str] = Counter()
        self.production_slots = asyncio.Semaphore(parallel_moments)
        self.clock: tuple[int, float] = (1, 0.0)
        self.commentary: deque[dict[str, object]] = deque(maxlen=COMMENTARY_HISTORY)
        self.frames: list[FrameRecord] = []
        self.played = 0
        self.clock_s = clock
        self.traces: dict[str, AgentTrace] = {}

    def describe(self) -> dict[str, object]:
        """Session summary for listings."""
        return {"session_id": self.session_id, "status": self.status.value, "speed": self.speed,
                "match": self.result.metadata.to_dict(), "subscribers": len(self.subscribers)}

    def snapshot(self) -> dict[str, object]:
        """Current interpreted state without the full moment list."""
        snap = self.service.analyzer.snapshot()
        snap.pop("moments", None)
        return snap

    def subscribe(self, profile: ViewerProfile) -> Subscriber:
        """Register a client for a segment and prime it with the current state."""
        is_new_segment = profile.viewer_id not in self.service.viewers
        if is_new_segment and len(self.service.viewers) >= MAX_SEGMENTS:
            raise SessionLimitError(f"At most {MAX_SEGMENTS} distinct viewer segments per match")
        backfill = self._backfill(profile) if is_new_segment else []
        subscriber = Subscriber(profile.viewer_id)
        self.subscribers.add(subscriber)
        self._send(subscriber, LiveMessage(MessageType.MATCH, self.describe()))
        self._send(subscriber, LiveMessage(MessageType.SNAPSHOT, self.snapshot()))
        for line in self.commentary:
            self._send(subscriber, LiveMessage(MessageType.COMMENTARY, line))
        for cue in self.cue_history.get(profile.viewer_id, ()):
            self._send(subscriber, LiveMessage(MessageType.CUE, cue | {"replay": True}))
        viewer = self.service.viewers[profile.viewer_id]
        for base, (context, recap) in zip(self.recaps, self.recap_sources, strict=True):
            take = template_take(context, viewer)
            self._send(subscriber, LiveMessage(MessageType.RECAP, base | _take_fields(viewer, take, OutputSource.FALLBACK)))
        if self.status is SessionStatus.FINISHED:
            self._spawn(self._end_after(subscriber, backfill))
        return subscriber

    async def _end_after(self, subscriber: Subscriber, pending: list[asyncio.Task[None]]) -> None:
        """Close a late subscriber's stream only after its backfilled cues have been delivered."""
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._send(subscriber, LiveMessage(MessageType.END, {"session_id": self.session_id}))

    def _backfill(self, profile: ViewerProfile) -> list[asyncio.Task[None]]:
        """Register a new segment and personalize the most recent relevant moments for it, watched or not."""
        viewer = self.service.add_viewer(profile)
        delivered = {cue["moment_id"] for cue in self.cue_history.get(profile.viewer_id, ())}
        recent = [c for c in self.recent_moments if is_relevant(c.moment, profile)][-BACKFILL_MOMENTS:]
        return [self._spawn(self._produce(MomentJob(c, (viewer,)), skip_if_stale=False))
                for c in recent if c.moment.moment_id not in delivered]

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a client; stop personalizing for its segment when nobody else watches it."""
        self.subscribers.discard(subscriber)
        if not any(s.segment_id == subscriber.segment_id for s in self.subscribers):
            self.service.remove_viewer(subscriber.segment_id)

    def _send(self, subscriber: Subscriber, message: LiveMessage) -> None:
        """Enqueue a message; for a slow subscriber the oldest queued message is dropped to make room."""
        if subscriber.queue.full():
            dropped = subscriber.queue.get_nowait()
            logger.warning("Dropped stale %s message for slow subscriber in %s", dropped.type, self.session_id)
        subscriber.queue.put_nowait(message)

    def publish(self, message: LiveMessage) -> None:
        """Deliver a message to every matching subscriber."""
        for subscriber in tuple(self.subscribers):
            if message.segment_id is None or message.segment_id == subscriber.segment_id:
                self._send(subscriber, message)

    def _spawn(self, coroutine: Awaitable[None]) -> asyncio.Task[None]:
        task = asyncio.ensure_future(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def _start_trace(self, job: MomentJob) -> AgentTrace:
        """Open a live trace for a moment entering production, keeping the newest TRACE_HISTORY traces."""
        moment = job.context.moment
        trace = AgentTrace(moment.moment_id, moment.minute_label, moment.kind.value, self.clock_s())
        self.traces[moment.moment_id] = trace
        for old in list(self.traces)[:-TRACE_HISTORY]:
            del self.traces[old]
        return trace

    async def _broadcast(self, job: MomentJob) -> MomentBroadcast:
        """Run the agent workflow; any unexpected failure degrades to templates instead of losing the moment."""
        trace = self._start_trace(job)
        try:
            return await self.service.produce(job, lambda executor, kind: trace.observe(executor, kind, self.clock_s()))
        except Exception:  # noqa: BLE001 - resilience boundary for background work
            logger.exception("Production failed for %s; publishing degraded cues", job.context.moment.moment_id)
            return degraded_broadcast(self.result.metadata.match_id, job.context, job)

    async def _produce(self, job: MomentJob, skip_if_stale: bool = True) -> None:
        """Wait for a production slot, then produce and publish the moment's cues.

        skip_if_stale defaults to True: a non-goal moment that fell behind the match clock while queued is skipped.
        Backfill for a new viewer passes False, because that viewer explicitly needs those moments.
        """
        moment = job.context.moment
        with _counting(self.queued, moment.moment_id):
            await self.production_slots.acquire()
        try:
            if skip_if_stale and is_stale(moment, *self.clock):
                logger.info("Skipped stale moment %s in %s", moment.moment_id, self.session_id)
                self.desk.skip(moment.moment_id)
                return
            with _counting(self.in_production, moment.moment_id):
                broadcast = await self._broadcast(job)
        finally:
            self.production_slots.release()
        record = self.desk.record(broadcast)
        if record.status is AirStatus.HELD:
            return
        self._air([cue.to_dict() for cue in broadcast.cues])

    def _air(self, cues: list[dict[str, object]]) -> None:
        for data in cues:
            segment = str(data["viewer_id"])
            self.cue_history.setdefault(segment, deque(maxlen=CUE_HISTORY)).append(data)
            self.publish(LiveMessage(MessageType.CUE, data, segment_id=segment))

    def set_hold(self, hold: bool) -> None:
        """Hold new AI overlays for producer approval, or air them immediately again."""
        self.desk.hold = hold

    def release(self, moment_id: str | None) -> int:
        """Air held overlays for one moment, or all held moments; returns how many cues were aired."""
        cues = self.desk.release(moment_id)
        self._air(cues)
        return len(cues)

    def spoken_line(self, ref: str, segment: str | None) -> tuple[str, str, Intensity]:
        """Text, language, and intensity of a commentary line this session produced, for spoken commentary."""
        return find_spoken_line(ref, segment, self.commentary, self.cue_history)

    def highlights(self, stage: RecapStage, segment: str | None) -> dict[str, object]:
        """The automated highlights reel for a recap stage, narrated for a viewer segment when given."""
        recap = next((r for r in self.recaps if r["stage"] == stage.value), None)
        if recap is None:
            raise HighlightsNotReadyError(f"Highlights for {stage.value} are ready once that recap is published")
        narrations = clip_narrations(self.cue_history.get(segment or "", ()), self.desk.records)
        clips = build_reel(self.service.analyzer.moments, stage, self.frames, narrations)
        headline = recap["recap"]["headline"] if isinstance(recap["recap"], dict) else ""
        return {"stage": stage.value, "headline": headline, "clips": [c.to_dict() for c in clips]}

    def studio(self, window: StudioWindow) -> dict[str, object]:
        """Studio analysis visuals over the events played so far, with the analyst's recommended visual."""
        return studio_payload(self.result.metadata, self.result.events[:self.played], self.frames, self.desk.records,
                              tuple(self.recent_moments), window)

    def producer_summary(self) -> dict[str, object]:
        """State for the producer console, including live agent traces for the newest moments."""
        summary = self.desk.summary(self.service.analyzer.moments, len(self.service.viewers),
                                    self.in_production.keys(), self.queued.keys())
        now = self.clock_s()
        traces = [trace.to_dict(now, self.desk.records[mid].cues if mid in self.desk.records else [])
                  for mid, trace in reversed(self.traces.items())]
        return summary | {"traces": traces}

    async def _recap(self, stage: RecapStage) -> None:
        """Write the shared recap, then publish it to each viewer segment with that segment's persona take."""
        context = build_recap_context(self.service.analyzer, stage)
        try:
            outcome = await self.service.recap(stage)
            recap, source, latency = outcome.value, outcome.source, outcome.latency_ms
        except Exception:  # noqa: BLE001 - resilience boundary for background work
            logger.exception("Recap failed for %s; publishing template recap", self.session_id)
            recap, source, latency = recap_template(context), OutputSource.FALLBACK, 0
        base = {"stage": stage.value, "recap": recap.model_dump(mode="json"), "source": source.value,
                "latency_ms": latency}
        self.recaps.append(base)
        self.recap_sources.append((context, recap))
        viewers = tuple(self.service.viewers.values())
        takes = await asyncio.gather(*(self._take(context, recap, v) for v in viewers))
        for viewer, (take, take_source) in zip(viewers, takes, strict=True):
            self.publish(LiveMessage(MessageType.RECAP, base | _take_fields(viewer, take, take_source),
                                     segment_id=viewer.viewer.viewer_id))

    async def _take(self, context: RecapContext, recap: MatchRecap, viewer: ViewerContext) -> tuple[RecapTake, OutputSource]:
        try:
            outcome = await self.service.recap_take(context, recap, viewer)
            return outcome.value, outcome.source
        except Exception:  # noqa: BLE001 - resilience boundary for background work
            logger.exception("Recap take failed for %s", viewer.viewer.viewer_id)
            return template_take(context, viewer), OutputSource.FALLBACK

    async def _drain(self) -> None:
        """Wait until no unfinished background work remains, including tasks spawned while waiting.

        Only unfinished tasks are awaited: finished tasks may linger in the set until their removal callback runs.
        """
        while pending := [task for task in self.tasks if not task.done()]:
            await asyncio.wait(pending)

    async def run(self) -> None:
        """Replay the match, drain agent work, and always finish with an end message."""
        self.status = SessionStatus.LIVE
        try:
            await self._replay()
            await self._drain()
        finally:
            self.status = SessionStatus.FINISHED
            self.publish(LiveMessage(MessageType.END, {"session_id": self.session_id}))

    def _keep_frame(self, event: MatchEvent, positions: Frame | None) -> None:
        """Store the tracking frame for highlights replays."""
        if positions is None:
            return
        ball = self.service.tracking.ball_home_frame
        self.frames.append(FrameRecord(event.period, event.match_second, event.event_type.value, event.player_id,
                                       (round(ball.x, BALL_DECIMALS), round(ball.y, BALL_DECIMALS)), positions))

    async def _replay(self) -> None:
        previous = None
        for index, event in enumerate(self.result.events):
            await self.sleep(replay_delay_s(previous, event, self.speed))
            self.clock = (event.period, event.match_second)
            upcoming = self.result.events[index + 1:index + 1 + LOOKAHEAD_EVENTS]
            interpretation = self.service.interpret(event, upcoming)
            sprint = interpretation.sprint
            self._keep_frame(event, interpretation.positions)
            self.played = index + 1
            payload = interpretation.update.to_dict() | {
                "positions": interpretation.positions,
                "sprint": {"player_id": sprint[0], "speed_kmh": sprint[1]} if sprint else None}
            self.publish(LiveMessage(MessageType.EVENT, payload))
            line = self.play_by_play.observe(interpretation.update)
            if line is not None:
                self.commentary.append(line.to_dict())
                self.publish(LiveMessage(MessageType.COMMENTARY, line.to_dict()))
            if index % SNAPSHOT_EVERY_EVENTS == 0 or interpretation.update.moments:
                self.publish(LiveMessage(MessageType.SNAPSHOT, self.snapshot()))
            self.recent_moments.extend(interpretation.contexts)
            for job in interpretation.jobs:
                self._spawn(self._produce(job))
            if interpretation.recap_stage:
                self._spawn(self._recap(interpretation.recap_stage))
            previous = event
