"""A live match session: replays events in real time and publishes results to subscribers.

Interpretation runs inline so the event feed keeps match pace, while agent workflows and recaps run as background
tasks that publish when ready. Cues are routed only to subscribers of the segment they were personalized for.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
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
from insidegame.core.exceptions import SessionLimitError
from insidegame.domain.match import MatchResult
from insidegame.live.pacing import replay_delay_s
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.service import MatchIntelligenceService, degraded_broadcast

logger = logging.getLogger(__name__)

QUEUE_MAX: int = 2000
CUE_HISTORY: int = 20
SNAPSHOT_EVERY_EVENTS: int = 25
BACKFILL_MOMENTS: int = 2
MAX_SEGMENTS: int = 10
MOMENT_HISTORY: int = 30

Sleeper = Callable[[float], Awaitable[None]]


class MessageType(StrEnum):
    """Kinds of messages streamed to clients."""

    MATCH = "match"
    EVENT = "event"
    SNAPSHOT = "snapshot"
    CUE = "cue"
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


def _take_fields(viewer: ViewerContext, take: RecapTake, source: OutputSource) -> dict[str, object]:
    return {"persona": viewer.viewer.persona.value, "take": take.model_dump(mode="json"), "take_source": source.value}


class MatchSession:
    """Owns one replayed match, its pipeline, and its subscribers."""

    def __init__(self, session_id: str, result: MatchResult, service: MatchIntelligenceService, speed: float,
                 sleep: Sleeper = asyncio.sleep) -> None:
        """Create a session; sleep defaults to asyncio.sleep and is injectable for tests."""
        self.session_id, self.result, self.service, self.speed, self.sleep = session_id, result, service, speed, sleep
        self.status = SessionStatus.PENDING
        self.subscribers: set[Subscriber] = set()
        self.cue_history: dict[str, deque[dict[str, object]]] = {}
        self.recaps: list[dict[str, object]] = []
        self.recap_sources: list[tuple[RecapContext, MatchRecap]] = []
        self.tasks: set[asyncio.Task[None]] = set()
        self.recent_moments: deque[MomentContext] = deque(maxlen=MOMENT_HISTORY)

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
        return [self._spawn(self._produce(MomentJob(c, (viewer,))))
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

    async def _produce(self, job: MomentJob) -> None:
        """Produce and publish cues; any unexpected failure degrades to templates instead of losing the moment."""
        try:
            broadcast = await self.service.produce(job)
        except Exception:  # noqa: BLE001 - resilience boundary for background work
            logger.exception("Production failed for %s; publishing degraded cues", job.context.moment.moment_id)
            broadcast = degraded_broadcast(self.result.metadata.match_id, job.context, job)
        for cue in broadcast.cues:
            data = cue.to_dict()
            self.cue_history.setdefault(cue.viewer_id, deque(maxlen=CUE_HISTORY)).append(data)
            self.publish(LiveMessage(MessageType.CUE, data, segment_id=cue.viewer_id))

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
        """Wait until no background work remains, including tasks spawned while waiting."""
        while self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)

    async def run(self) -> None:
        """Replay the match, drain agent work, and always finish with an end message."""
        self.status = SessionStatus.LIVE
        try:
            await self._replay()
            await self._drain()
        finally:
            self.status = SessionStatus.FINISHED
            self.publish(LiveMessage(MessageType.END, {"session_id": self.session_id}))

    async def _replay(self) -> None:
        previous = None
        for index, event in enumerate(self.result.events):
            await self.sleep(replay_delay_s(previous, event, self.speed))
            interpretation = self.service.interpret(event)
            self.publish(LiveMessage(MessageType.EVENT, interpretation.update.to_dict()))
            if index % SNAPSHOT_EVERY_EVENTS == 0 or interpretation.update.moments:
                self.publish(LiveMessage(MessageType.SNAPSHOT, self.snapshot()))
            self.recent_moments.extend(interpretation.contexts)
            for job in interpretation.jobs:
                self._spawn(self._produce(job))
            if interpretation.recap_stage:
                self._spawn(self._recap(interpretation.recap_stage))
            previous = event
