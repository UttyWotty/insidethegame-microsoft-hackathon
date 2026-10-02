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

from insidegame.agents.personas import ViewerProfile
from insidegame.agents.recap_context import RecapStage
from insidegame.domain.match import MatchResult
from insidegame.live.pacing import replay_delay_s
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.service import MatchIntelligenceService

logger = logging.getLogger(__name__)

QUEUE_MAX: int = 2000
CUE_HISTORY: int = 20
SNAPSHOT_EVERY_EVENTS: int = 25

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
        self.tasks: set[asyncio.Task[None]] = set()

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
        if profile.viewer_id not in self.service.viewers:
            self.service.add_viewer(profile)
        subscriber = Subscriber(profile.viewer_id)
        self.subscribers.add(subscriber)
        self._send(subscriber, LiveMessage(MessageType.MATCH, self.describe()))
        self._send(subscriber, LiveMessage(MessageType.SNAPSHOT, self.snapshot()))
        for cue in self.cue_history.get(profile.viewer_id, ()):
            self._send(subscriber, LiveMessage(MessageType.CUE, cue))
        for recap in self.recaps:
            self._send(subscriber, LiveMessage(MessageType.RECAP, recap))
        if self.status is SessionStatus.FINISHED:
            self._send(subscriber, LiveMessage(MessageType.END, {"session_id": self.session_id}))
        return subscriber

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

    def _spawn(self, coroutine: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _produce(self, job: MomentJob) -> None:
        broadcast = await self.service.produce(job)
        for cue in broadcast.cues:
            data = cue.to_dict()
            self.cue_history.setdefault(cue.viewer_id, deque(maxlen=CUE_HISTORY)).append(data)
            self.publish(LiveMessage(MessageType.CUE, data, segment_id=cue.viewer_id))

    async def _recap(self, stage: RecapStage) -> None:
        outcome = await self.service.recap(stage)
        data = {"stage": stage.value, "recap": outcome.value.model_dump(mode="json"),
                "source": outcome.source.value, "latency_ms": outcome.latency_ms}
        self.recaps.append(data)
        self.publish(LiveMessage(MessageType.RECAP, data))

    async def run(self) -> None:
        """Replay the match at session speed, then wait for outstanding agent work."""
        self.status = SessionStatus.LIVE
        previous = None
        for index, event in enumerate(self.result.events):
            await self.sleep(replay_delay_s(previous, event, self.speed))
            interpretation = self.service.interpret(event)
            self.publish(LiveMessage(MessageType.EVENT, interpretation.update.to_dict()))
            if index % SNAPSHOT_EVERY_EVENTS == 0 or interpretation.update.moments:
                self.publish(LiveMessage(MessageType.SNAPSHOT, self.snapshot()))
            for job in interpretation.jobs:
                self._spawn(self._produce(job))
            if interpretation.recap_stage:
                self._spawn(self._recap(interpretation.recap_stage))
            previous = event
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks))
        self.status = SessionStatus.FINISHED
        self.publish(LiveMessage(MessageType.END, {"session_id": self.session_id}))
