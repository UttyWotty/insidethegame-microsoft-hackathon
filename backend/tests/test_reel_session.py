"""End-to-end tests of the highlights reel's shot stories on the seed-201 demo fixture, run through a real MatchSession.

The session uses the offline agent policy and an instant sleeper, so the full match plays in seconds while the
stored frames and threats come from the same interpretation code the broadcast runs.
They pin that every shot clip replays exactly the instant replay's keyframes, ending with the ball on the goal line.
"""

import asyncio

import pytest
from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.factory import create_agent_suite
from insidegame.agents.recap_context import RecapStage
from insidegame.agents.runner import RunPolicy
from insidegame.live.session import MatchSession
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
DEMO_SEED = 201
SPEED = 30.0
FULL_TIME_MINUTES = ["15'", "19'", "35'", "36'", "62'", "77'"]
ASSIST_START = [99.0, 3.6]
GOAL_LINE_X = 105.0
LINE_TOLERANCE_M = 0.01
POST_Y = (30.34, 37.66)


async def _instant(seconds: float) -> None:
    await asyncio.sleep(0)


@pytest.fixture(scope="module")
def session() -> MatchSession:
    async def scenario() -> MatchSession:
        result = simulate_match(build_fixture("kestrel_bay", "ironvale", DEMO_SEED))
        client = OpenAIChatCompletionClient(model="unused", base_url="http://127.0.0.1:9", api_key="x")
        service = MatchIntelligenceService(result.metadata, create_agent_suite(client), OFFLINE_POLICY, viewers=())
        live = MatchSession("demo", result, service, SPEED, _instant)
        await live.run()
        return live

    return asyncio.run(scenario())


def _clips(session: MatchSession, stage: RecapStage) -> list[dict]:
    clips = session.highlights(stage, None)["clips"]
    assert isinstance(clips, list)
    return clips


def test_full_time_goal_clips_replay_the_instant_replay_story(session: MatchSession) -> None:
    clips = _clips(session, RecapStage.FULL_TIME)
    assert [c["minute"] for c in clips] == FULL_TIME_MINUTES
    assert {c["kind"] for c in clips} == {"goal"} and {c["playback"] for c in clips} == {"story"}
    for clip in clips:
        assert clip["frames"] == session.replay(clip["period"], round(clip["match_second"], 2))["frames"]


def test_the_77th_minute_winner_shows_the_assist_and_ends_on_the_goal_line(session: MatchSession) -> None:
    winner = _clips(session, RecapStage.FULL_TIME)[-1]
    frames = winner["frames"]
    assert any(k["phase"] == "build_up" and k["ball"] == ASSIST_START for k in frames)
    last = frames[-1]
    assert last["phase"] == "flight"
    assert abs(last["ball"][0] - GOAL_LINE_X) <= LINE_TOLERANCE_M and POST_Y[0] <= last["ball"][1] <= POST_Y[1]
    times = [k["match_second"] for k in frames]
    assert times == sorted(times)


def test_half_time_hat_trick_milestone_and_big_chance_play_stories(session: MatchSession) -> None:
    clips = _clips(session, RecapStage.HALF_TIME)
    milestone = next(c for c in clips if c["kind"] == "milestone" and c["minute"] == "35'")
    goal = next(c for c in clips if c["kind"] == "goal" and c["minute"] == "35'")
    assert milestone["playback"] == "story" and milestone["frames"] == goal["frames"]
    chance = next(c for c in clips if c["kind"] == "big_chance_missed" and c["minute"] == "3'")
    assert chance["playback"] == "story" and chance["frames"][-1]["phase"] == "flight"
