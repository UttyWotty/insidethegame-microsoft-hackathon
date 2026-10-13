"""Tests for moment production backpressure: limited production slots and skipping moments that went stale.

The staleness rule is tested directly; the session test blocks model work until the replay reaches full time, so
exactly the moments that took the first slots are produced and every later non-goal moment is skipped as stale.
"""

import asyncio

from test_live import GOALS_SEED, OFFLINE_POLICY, _consume, _offline_suite

from insidegame.analytics.moments import KeyMoment, MomentKind
from insidegame.live.segments import build_segment_profile
from insidegame.live.session import DEFAULT_PARALLEL_MOMENTS, MatchSession
from insidegame.orchestration.cues import MomentBroadcast
from insidegame.orchestration.messages import MomentJob
from insidegame.orchestration.producer import STALE_MOMENT_MATCH_S, is_stale
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

SPEED = 10.0
MOMENT_SECOND = 600.0
IMPORTANCE = 0.5


def _moment(kind: MomentKind) -> KeyMoment:
    return KeyMoment("m", kind, 1, MOMENT_SECOND, IMPORTANCE, None)


def _finished_session() -> tuple[MatchSession, int]:
    async def scenario() -> tuple[MatchSession, int]:
        result = simulate_match(build_fixture("brookhaven", "silverlake", GOALS_SEED))
        service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, ())
        full_time = asyncio.Event()
        replayed = 0

        async def sleeper(seconds: float) -> None:
            nonlocal replayed
            replayed += 1
            if replayed == len(result.events):
                full_time.set()
            await asyncio.sleep(0)

        session = MatchSession("bp", result, service, SPEED, sleeper)
        original, active, peak = service.produce, 0, 0

        async def blocked(job: MomentJob) -> MomentBroadcast:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await full_time.wait()
            try:
                return await original(job)
            finally:
                active -= 1

        service.produce = blocked  # type: ignore[method-assign]
        viewer = session.subscribe(build_segment_profile("analyst"))
        await asyncio.gather(session.run(), _consume(viewer.queue))
        return session, peak

    return asyncio.run(scenario())


def test_goals_never_go_stale_and_other_moments_expire_by_period_and_age() -> None:
    goal, save = _moment(MomentKind.GOAL), _moment(MomentKind.GREAT_SAVE)
    late = MOMENT_SECOND + STALE_MOMENT_MATCH_S + 1
    assert not is_stale(goal, 2, late)
    assert not is_stale(save, 1, MOMENT_SECOND + STALE_MOMENT_MATCH_S)
    assert is_stale(save, 1, late) and is_stale(save, 2, MOMENT_SECOND)


def test_slow_production_respects_slots_skips_stale_moments_and_still_airs_goals() -> None:
    session, peak = _finished_session()
    assert peak == DEFAULT_PARALLEL_MOMENTS
    moments = {m.moment_id: m for m in session.service.analyzer.moments}
    kinds = {mid: m.kind for mid, m in moments.items()}
    full_time = (session.result.events[-1].period, session.result.events[-1].match_second)
    assert session.desk.skipped and all(is_stale(moments[mid], *full_time) for mid in session.desk.skipped)
    early_slots = [mid for mid in session.desk.records if is_stale(moments[mid], *full_time)]
    assert len(early_slots) <= DEFAULT_PARALLEL_MOMENTS
    summary = session.producer_summary()
    statuses = {t["moment_id"]: t["status"] for t in summary["timeline"]}  # type: ignore[union-attr]
    assert all(statuses[mid] == "aired" for mid, kind in kinds.items() if kind is MomentKind.GOAL)
    assert summary["health"]["skipped"] == len(session.desk.skipped)  # type: ignore[index]
    assert not session.queued and not session.in_production
