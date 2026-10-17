"""End-to-end tests of the highlights reel's shot stories on the demo fixture (DEMO_SEED), run through a real MatchSession.

The session uses the offline agent policy and an instant sleeper, so the full match plays in seconds while the
stored frames and threats come from the same interpretation code the broadcast runs.
They pin that every shot clip replays exactly the instant replay's keyframes, ending with the ball on the goal line.
The demo match has no goal milestone, so MILESTONE_SEED (seed 28: Felix Delacroix's brace at 26', in the half-time
reel) checks that a milestone clip shares its goal's frames.
"""

import asyncio

import pytest
from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.factory import create_agent_suite
from insidegame.agents.runner import RunPolicy
from insidegame.analytics.recap_basis import RecapStage
from insidegame.live.session import MatchSession
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_SEED, build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
MILESTONE_SEED = 28
SPEED = 30.0
FULL_TIME_CLIPS = [("big_chance_missed", "20'", "story"), ("great_save", "20'", "story"), ("goal", "28'", "story"),
                   ("goal", "34'", "story"), ("goal", "65'", "story"), ("big_chance_missed", "89'", "story")]
HALF_TIME_CLIPS = [("big_chance_missed", "20'", "story"), ("great_save", "20'", "story"),
                   ("momentum_swing", "23'", "frames"), ("great_save", "23'", "story"), ("goal", "28'", "story"),
                   ("goal", "34'", "story")]
WINNER_INDEX = 4
ASSIST_RECEPTION = [91.7, 25.2]
WINNER_SCORER = "kba-09"
GOAL_LINE_X = 105.0
LINE_TOLERANCE_M = 0.01
POST_Y = (30.34, 37.66)


async def _instant(seconds: float) -> None:
    await asyncio.sleep(0)


def _played(seed: int) -> MatchSession:
    async def scenario() -> MatchSession:
        result = simulate_match(build_fixture("kestrel_bay", "ironvale", seed))
        client = OpenAIChatCompletionClient(model="unused", base_url="http://127.0.0.1:9", api_key="x")
        service = MatchIntelligenceService(result.metadata, create_agent_suite(client), OFFLINE_POLICY, viewers=())
        live = MatchSession("demo", result, service, SPEED, _instant)
        await live.run()
        return live

    return asyncio.run(scenario())


@pytest.fixture(scope="module")
def session() -> MatchSession:
    return _played(DEMO_SEED)


@pytest.fixture(scope="module")
def milestone_session() -> MatchSession:
    return _played(MILESTONE_SEED)


def _clips(session: MatchSession, stage: RecapStage) -> list[dict]:
    clips = session.highlights(stage, None)["clips"]
    assert isinstance(clips, list)
    return clips


def _clip_ids(clips: list[dict]) -> list[tuple[str, str, str]]:
    return [(c["kind"], c["minute"], c["playback"]) for c in clips]


def test_full_time_shot_clips_replay_the_instant_replay_story(session: MatchSession) -> None:
    clips = _clips(session, RecapStage.FULL_TIME)
    assert _clip_ids(clips) == FULL_TIME_CLIPS
    stories = [c for c in clips if c["playback"] == "story"]
    assert stories and {c["kind"] for c in stories} >= {"goal", "great_save", "big_chance_missed"}
    for clip in stories:
        assert clip["frames"] == session.replay(clip["period"], round(clip["match_second"], 2))["frames"]


def test_the_65th_minute_winner_shows_the_build_up_and_ends_on_the_goal_line(session: MatchSession) -> None:
    winner = _clips(session, RecapStage.FULL_TIME)[WINNER_INDEX]
    assert (winner["kind"], winner["minute"]) == ("goal", "65'")
    frames = winner["frames"]
    first = frames[0]
    assert first["phase"] == "build_up" and first["ball"] == ASSIST_RECEPTION and first["player_id"] == WINNER_SCORER
    last = frames[-1]
    assert last["phase"] == "flight"
    assert abs(last["ball"][0] - GOAL_LINE_X) <= LINE_TOLERANCE_M and POST_Y[0] <= last["ball"][1] <= POST_Y[1]
    times = [k["match_second"] for k in frames]
    assert times == sorted(times)


def test_half_time_big_chance_and_saves_play_stories(session: MatchSession) -> None:
    clips = _clips(session, RecapStage.HALF_TIME)
    assert _clip_ids(clips) == HALF_TIME_CLIPS
    chance = next(c for c in clips if c["kind"] == "big_chance_missed" and c["minute"] == "20'")
    assert chance["playback"] == "story" and chance["frames"][-1]["phase"] == "flight"
    saves = [c for c in clips if c["kind"] == "great_save"]
    assert saves and all(c["playback"] == "story" and c["frames"][-1]["phase"] == "flight" for c in saves)


def test_half_time_brace_milestone_shares_its_goal_frames(milestone_session: MatchSession) -> None:
    clips = _clips(milestone_session, RecapStage.HALF_TIME)
    milestone = next(c for c in clips if c["kind"] == "milestone" and c["minute"] == "26'")
    goal = next(c for c in clips if c["kind"] == "goal" and c["minute"] == "26'")
    assert milestone["playback"] == "story" and milestone["frames"] == goal["frames"]
