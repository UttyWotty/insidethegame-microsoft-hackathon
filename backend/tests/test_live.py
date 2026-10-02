"""Tests for replay pacing, viewer segments, and live session fan-out.

Sessions run with the offline policy (zero model attempts) and an instant sleeper, so a full match replays in
milliseconds while exercising the real interpretation, workflow, and routing code.
"""

import asyncio

import pytest
from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.factory import create_agent_suite
from insidegame.agents.personas import PersonaKey
from insidegame.agents.runner import RunPolicy
from insidegame.core.exceptions import PersonaConfigError
from insidegame.domain.events import MatchEvent
from insidegame.live.pacing import HALF_TIME_BREAK_MATCH_S, replay_delay_s
from insidegame.live.segments import build_segment_profile, segment_id
from insidegame.live.session import LiveMessage, MatchSession, MessageType, SessionStatus
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
SPEED = 10.0


async def _instant(seconds: float) -> None:
    await asyncio.sleep(0)


def _offline_suite():  # noqa: ANN202
    return create_agent_suite(OpenAIChatCompletionClient(model="unused", base_url="http://127.0.0.1:9", api_key="x"))


def _event(second: float, period: int) -> MatchEvent:
    from insidegame.domain.enums import EventType
    return MatchEvent("e", "m", 0, period, second, EventType.PASS, "t", "p", 0, None, 0, 0)


def test_replay_delay_scales_with_speed_and_compresses_half_time() -> None:
    assert replay_delay_s(None, _event(0, 1), SPEED) == 0.0
    assert replay_delay_s(_event(100, 1), _event(130, 1), SPEED) == 3.0
    assert replay_delay_s(_event(2900, 1), _event(2700, 2), SPEED) == HALF_TIME_BREAK_MATCH_S / SPEED


def test_segment_ids_are_deterministic_and_validated() -> None:
    profile = build_segment_profile("superfan", "es", "kba", None)
    assert profile.viewer_id == segment_id(PersonaKey.SUPERFAN, "es", "kba", None)
    with pytest.raises(PersonaConfigError):
        build_segment_profile("pundit")
    with pytest.raises(PersonaConfigError):
        build_segment_profile("analyst", "english")


def _drain(queue: asyncio.Queue[LiveMessage]) -> list[LiveMessage]:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


async def _consume(queue: asyncio.Queue[LiveMessage]) -> list[LiveMessage]:
    messages = [await queue.get()]
    while messages[-1].type is not MessageType.END:
        messages.append(await queue.get())
    return messages


async def _run_session() -> tuple[MatchSession, list[LiveMessage], list[LiveMessage], list[LiveMessage]]:
    result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
    service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, viewers=())
    session = MatchSession("s1", result, service, SPEED, _instant)
    analyst = session.subscribe(build_segment_profile("analyst"))
    casual = session.subscribe(build_segment_profile("casual", "de"))
    _, analyst_messages, casual_messages = await asyncio.gather(
        session.run(), _consume(analyst.queue), _consume(casual.queue))
    late = session.subscribe(build_segment_profile("analyst"))
    return session, analyst_messages, casual_messages, _drain(late.queue)


def test_session_streams_every_event_and_routes_cues_by_segment() -> None:
    session, analyst, casual, late = asyncio.run(_run_session())
    types = [m.type for m in analyst]
    assert types[0] is MessageType.MATCH and types[-1] is MessageType.END
    assert types.count(MessageType.EVENT) == len(session.result.events)
    assert types.count(MessageType.RECAP) == 2
    analyst_cues = [m for m in analyst if m.type is MessageType.CUE]
    casual_cues = [m for m in casual if m.type is MessageType.CUE]
    assert analyst_cues and casual_cues and len(analyst_cues) > len(casual_cues)
    assert all(m.data["persona"] == "casual" and m.data["language"] == "en"
               and m.data["provenance"]["translation"]["source"] == "fallback" for m in casual_cues)
    assert session.status is SessionStatus.FINISHED


def test_late_subscriber_receives_history_and_end() -> None:
    _, _, _, late = asyncio.run(_run_session())
    types = [m.type for m in late]
    assert MessageType.CUE in types and types.count(MessageType.RECAP) == 2
    assert types[-1] is MessageType.END


def test_slow_subscriber_keeps_the_newest_messages() -> None:
    async def scenario() -> list[LiveMessage]:
        result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
        service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, viewers=())
        session = MatchSession("s2", result, service, SPEED, _instant)
        sleepy = session.subscribe(build_segment_profile("analyst"))
        await session.run()
        return _drain(sleepy.queue)

    messages = asyncio.run(scenario())
    assert messages[-1].type is MessageType.END
    assert sum(m.type is MessageType.RECAP for m in messages) == 2


def test_new_segment_mid_match_is_backfilled_with_recent_moments() -> None:
    async def scenario() -> list[LiveMessage]:
        result = simulate_match(build_fixture("brookhaven", "silverlake", 3))
        service = MatchIntelligenceService(result.metadata, _offline_suite(), OFFLINE_POLICY, viewers=())
        session = MatchSession("s3", result, service, SPEED, _instant)
        early = session.subscribe(build_segment_profile("analyst"))
        await asyncio.gather(session.run(), _consume(early.queue))
        late = session.subscribe(build_segment_profile("newcomer", "fr"))
        await asyncio.gather(*tuple(session.tasks))
        return _drain(late.queue)

    cues = [m for m in asyncio.run(scenario()) if m.type is MessageType.CUE]
    assert cues and all(m.data["persona"] == "newcomer" for m in cues)
