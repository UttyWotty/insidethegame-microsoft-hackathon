"""Tests for the producer desk: holding AI overlays, releasing them, auditing records, and the console API.

Sessions run offline with an instant sleeper, so a whole match is produced in milliseconds.
The API tests cover the summary, hold and release endpoints, and the optional producer key.
"""

import asyncio

import pytest
from test_api import _client
from test_live import OFFLINE_POLICY, SPEED, _consume, _drain, _instant, _offline_suite

from insidegame.api import routes_producer
from insidegame.live.segments import build_segment_profile
from insidegame.live.session import MatchSession, MessageType
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

GOALS_SEED = 1  # a seed whose match has goals, so every persona receives cues and some moments do not air


def _session() -> MatchSession:
    result = simulate_match(build_fixture("brookhaven", "silverlake", GOALS_SEED))
    return MatchSession("p", result, MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, ()),
                        SPEED, _instant)


def test_held_moments_do_not_air_until_released() -> None:
    async def scenario() -> tuple[int, int, dict[str, object]]:
        session = _session()
        session.set_hold(True)
        viewer = session.subscribe(build_segment_profile("analyst"))
        messages = (await asyncio.gather(session.run(), _consume(viewer.queue)))[1]
        before = sum(m.type is MessageType.CUE for m in messages)
        first_held = next(r for r in session.desk.records.values())
        released = session.release(first_held.moment_id)
        after = sum(m.type is MessageType.CUE for m in _drain(viewer.queue))
        return before, after if released else -1, session.producer_summary()

    before, after, summary = asyncio.run(scenario())
    assert before == 0 and after >= 1
    statuses = {r["status"] for r in summary["records"]}  # type: ignore[index]
    assert statuses == {"held", "released"}


def test_summary_reports_timeline_and_pipeline_health() -> None:
    async def scenario() -> dict[str, object]:
        session = _session()
        viewer = session.subscribe(build_segment_profile("casual"))
        await asyncio.gather(session.run(), _consume(viewer.queue))
        return session.producer_summary()

    summary = asyncio.run(scenario())
    timeline, health = summary["timeline"], summary["health"]
    assert any(t["status"] == "aired" for t in timeline) and any(t["status"] == "not_aired" for t in timeline)  # type: ignore[union-attr]
    assert health["cues"] > 0 and health["source_rates"]["card"] == {"fallback": 1.0}  # type: ignore[index]


def test_moments_still_being_produced_are_reported_in_production() -> None:
    async def scenario() -> MatchSession:
        session = _session()
        viewer = session.subscribe(build_segment_profile("casual"))
        await asyncio.gather(session.run(), _consume(viewer.queue))
        return session

    session = asyncio.run(scenario())
    moments = session.service.analyzer.moments
    pending = next(m.moment_id for m in moments if m.moment_id not in session.desk.records)
    timeline = session.desk.summary(moments, 1, {pending})["timeline"]
    statuses = {t["moment_id"]: t["status"] for t in timeline}  # type: ignore[union-attr]
    assert [moment for moment, status in statuses.items() if status == "in_production"] == [pending]
    assert not session.in_production


def test_console_api_and_optional_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={}).json()["session_id"]
        base = f"/api/matches/{session_id}/producer"
        assert client.post(f"{base}/hold", json={"on": True}).json() == {"hold": True}
        assert client.get(base).json()["hold"] is True
        assert client.post(f"{base}/release", json={}).json()["released_cues"] >= 0
        monkeypatch.setattr(routes_producer, "PRODUCER_KEY", "secret")
        assert client.get(base).status_code == 403
        assert client.get(base, headers={"x-producer-key": "secret"}).status_code == 200
