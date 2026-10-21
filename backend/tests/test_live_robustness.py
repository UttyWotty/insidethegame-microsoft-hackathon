"""Robustness tests for live sessions: failing background work, the full-time drain, and reconnect backfill.

A wrapper service injects failures, delays, and call counting around the real offline pipeline.
Each test pins a defect found in review so it cannot return.
"""

import asyncio

from test_live import OFFLINE_POLICY, SPEED, _consume, _instant, _offline_suite

from insidegame.live.segments import build_segment_profile
from insidegame.live.session import LiveMessage, MatchSession, MessageType, SessionStatus
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture


class FaultyService(MatchIntelligenceService):
    """Offline service that can fail, pause, and count production calls."""

    def __init__(self, *args: object, fail_recap: bool = False, fail_produce: bool = False,
                 gate: asyncio.Event | None = None) -> None:
        super().__init__(*args)  # type: ignore[arg-type]
        self.fail_recap, self.fail_produce, self.gate, self.produced = fail_recap, fail_produce, gate, 0

    async def produce(self, job: MomentJob, observer: object = None):  # type: ignore[no-untyped-def]
        self.produced += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.fail_produce:
            raise RuntimeError("produce boom")
        return await super().produce(job)

    async def recap(self, stage):  # type: ignore[no-untyped-def]
        if self.fail_recap:
            raise RuntimeError("recap boom")
        return await super().recap(stage)


def _session(**faults: object) -> MatchSession:
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
    service = FaultyService(result.metadata, _offline_suite(), OFFLINE_POLICY, (), **faults)
    return MatchSession("r", result, service, SPEED, _instant)


def test_failing_background_work_still_ends_the_match_with_fallbacks() -> None:
    async def scenario() -> tuple[MatchSession, list[LiveMessage]]:
        session = _session(fail_recap=True, fail_produce=True)
        viewer = session.subscribe(build_segment_profile("analyst"))
        _, messages = await asyncio.gather(session.run(), _consume(viewer.queue))
        return session, messages

    session, messages = asyncio.run(scenario())
    types = [m.type for m in messages]
    assert session.status is SessionStatus.FINISHED and types[-1] is MessageType.END
    assert types.count(MessageType.RECAP) == 2
    assert all(m.data["source"] == "fallback" for m in messages if m.type is MessageType.RECAP)
    cues = [m for m in messages if m.type is MessageType.CUE]
    assert cues and all(m.data["provenance"]["card"]["source"] == "fallback" for m in cues)


def test_subscriber_joining_during_the_final_drain_gets_backfill_before_end() -> None:
    async def scenario() -> list[LiveMessage]:
        gate = asyncio.Event()
        session = _session(gate=gate)
        early = session.subscribe(build_segment_profile("analyst"))
        runner = asyncio.ensure_future(session.run())
        early_consumer = asyncio.ensure_future(_consume(early.queue))
        while session.service.analyzer.last_event is not session.result.events[-1]:
            await asyncio.sleep(0)
        late = session.subscribe(build_segment_profile("newcomer", "fr"))
        gate.set()
        late_messages = await _consume(late.queue)
        await asyncio.gather(runner, early_consumer)
        return late_messages

    types = [m.type for m in asyncio.run(scenario())]
    assert MessageType.CUE in types and types[-1] is MessageType.END


def test_reconnecting_segment_does_not_reproduce_cues_it_already_has() -> None:
    async def scenario() -> tuple[int, int]:
        session = _session()
        await session.run()
        first = session.subscribe(build_segment_profile("analyst"))
        await _consume(first.queue)
        session.unsubscribe(first)
        produced_once = session.service.produced  # type: ignore[attr-defined]
        again = session.subscribe(build_segment_profile("analyst"))
        await _consume(again.queue)
        return produced_once, session.service.produced  # type: ignore[attr-defined]

    produced_once, produced_total = asyncio.run(scenario())
    assert produced_once > 0 and produced_total == produced_once


def test_registry_shutdown_cancels_replays_and_agent_work() -> None:
    from insidegame.live.registry import SessionRegistry

    async def never_ending(seconds: float) -> None:
        await asyncio.sleep(3600)

    async def scenario() -> tuple[bool, bool]:
        registry = SessionRegistry(_offline_suite(), OFFLINE_POLICY, never_ending)
        session = registry.create("brookhaven", "silverlake", 3, SPEED)
        blocker = session._spawn(asyncio.sleep(3600))
        await asyncio.sleep(0)
        await registry.shutdown()
        return all(t.done() for t in registry.runners.values()), blocker.cancelled()

    runners_done, work_cancelled = asyncio.run(scenario())
    assert runners_done and work_cancelled
