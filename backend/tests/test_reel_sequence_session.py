"""End-to-end tests of non-shot highlights clips on real matches (seeds 194 and 2), run through a real MatchSession.

The session uses the offline agent policy and an instant sleeper, so each match plays in seconds while the stored
events and frames come from the same interpretation code the broadcast runs.
They pin the measured window keyframes of a momentum swing and line-breaking passes, keep the acting player on the
ball in every non-shot clip, and keep every shot clip equal to the instant replay.
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
from insidegame.simulation.roster import build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
SPEED = 30.0
SWING_SEED = 194
PASS_SEED = 2
SWING_HALF_TIME_CLIPS = [("great_save", "20'", "story"), ("momentum_swing", "22'", "story"),
                         ("great_save", "26'", "story"), ("big_chance_missed", "28'", "story"),
                         ("goal", "28'", "story")]
SWING_BALLS = [[70.2, 62.5], [56.7, 68.0], [56.7, 68.0], [54.2, 58.6], [54.2, 58.6], [48.4, 60.4],
               [35.3, 60.3]]
THREAT_KEYFRAMES = 10
THREAT_FIRST_BALL = [67.4, 64.0]
THREAT_LAST_BALL = [99.0, 38.0]
THREAT_RECEIVER = "kba-08"
PASS_SEED_LAST_BALLS = {"10'": [73.0, 0.0], "23'": [8.3, 21.4]}


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
def swing_session() -> MatchSession:
    return _played(SWING_SEED)


@pytest.fixture(scope="module")
def pass_session() -> MatchSession:
    return _played(PASS_SEED)


def _clips(session: MatchSession, stage: RecapStage) -> list[dict]:
    clips = session.highlights(stage, None)["clips"]
    assert isinstance(clips, list)
    return clips


def _has_shot(clip: dict) -> bool:
    return any(k.get("phase") == "shot" for k in clip["frames"])


def _half_time_clip(session: MatchSession, minute: str) -> dict:
    return next(c for c in _clips(session, RecapStage.HALF_TIME) if c["minute"] == minute and not _has_shot(c))


def test_seed_194_momentum_swing_plays_its_window_actions(swing_session: MatchSession) -> None:
    clips = _clips(swing_session, RecapStage.HALF_TIME)
    assert [(c["kind"], c["minute"], c["playback"]) for c in clips] == SWING_HALF_TIME_CLIPS
    swing = _half_time_clip(swing_session, "22'")
    assert {k["phase"] for k in swing["frames"]} == {"build_up"}
    assert [k["ball"] for k in swing["frames"]] == SWING_BALLS


def test_seed_2_line_breaking_pass_ends_with_the_receiver(pass_session: MatchSession) -> None:
    threat = _half_time_clip(pass_session, "3'")
    frames = threat["frames"]
    assert (threat["kind"], threat["playback"]) == ("threat_created", "story")
    assert len(frames) == THREAT_KEYFRAMES and {k["phase"] for k in frames} == {"build_up"}
    assert frames[0]["ball"] == THREAT_FIRST_BALL
    assert frames[-1]["ball"] == THREAT_LAST_BALL and frames[-1]["player_id"] == THREAT_RECEIVER


@pytest.mark.parametrize("minute, ball", list(PASS_SEED_LAST_BALLS.items()))
def test_seed_2_other_non_shot_clips_land_on_the_measured_ball(pass_session: MatchSession, minute: str,
                                                                ball: list[float]) -> None:
    clip = _half_time_clip(pass_session, minute)
    assert clip["playback"] == "story" and clip["frames"][-1]["ball"] == ball


@pytest.mark.parametrize("which", ["swing", "pass"])
def test_non_shot_clips_move_forward_with_the_actor_on_the_ball(swing_session: MatchSession,
                                                                 pass_session: MatchSession, which: str) -> None:
    session = swing_session if which == "swing" else pass_session
    clips = [c for stage in RecapStage for c in _clips(session, stage) if not _has_shot(c)]
    assert clips
    for clip in clips:
        times = [k["match_second"] for k in clip["frames"]]
        assert times == sorted(times)
        if clip["playback"] != "story":
            continue
        for k in clip["frames"]:
            spots = {p[0]: [p[1], p[2]] for p in k["positions"]}
            assert k["player_id"] is None or spots[k["player_id"]] == k["ball"]


@pytest.mark.parametrize("which", ["swing", "pass"])
def test_shot_clips_still_equal_the_instant_replay(swing_session: MatchSession, pass_session: MatchSession,
                                                   which: str) -> None:
    session = swing_session if which == "swing" else pass_session
    shots = [c for stage in RecapStage for c in _clips(session, stage) if _has_shot(c)]
    assert shots
    for clip in shots:
        assert clip["frames"] == session.replay(clip["period"], round(clip["match_second"], 2))["frames"]


FAILED_PASS_SEED = 5
FAILED_PASS_MINUTE = "25'"
FAILED_PASS_INTENDED = "kba-11"


@pytest.fixture(scope="module")
def failed_pass_session() -> MatchSession:
    return _played(FAILED_PASS_SEED)


def test_seed_5_swing_ending_on_an_intercepted_pass_does_not_hand_the_ball_to_the_intended_receiver(
        failed_pass_session: MatchSession) -> None:
    """Seed 5's 25' swing ends on kba-02's failed pass to kba-11, which irv-05 intercepts 2 m from the end spot."""
    clip = _half_time_clip(failed_pass_session, FAILED_PASS_MINUTE)
    assert clip["playback"] == "story"
    before, arrival = clip["frames"][-2], clip["frames"][-1]
    assert arrival["player_id"] != FAILED_PASS_INTENDED
    assert arrival["positions"] == before["positions"]
