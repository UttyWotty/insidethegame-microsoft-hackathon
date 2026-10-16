"""End-to-end tests of instant replay stories on the seed-201 demo fixture, run through a real MatchSession.

The session uses the offline agent policy and an instant sleeper, so the full match plays in seconds while the
stored frames and threats come from the same interpretation code the broadcast runs.
They pin the measured numbers of the 15' and 77' goals and the keyframe invariants every shot replay must keep.
"""

import asyncio

import pytest
from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.factory import create_agent_suite
from insidegame.agents.runner import RunPolicy
from insidegame.core.exceptions import ReplayNotFoundError
from insidegame.core.geometry import Point, distance
from insidegame.highlights.replay_story import REPLAY_MAX_LEAD_S
from insidegame.live.session import MatchSession
from insidegame.orchestration.service import MatchIntelligenceService
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
DEMO_SEED = 201
SPEED = 30.0
WINNER = (2, 4574.03)
OPENER = (1, 883.59)
GOAL_LINES = (0.0, 105.0)
LINE_TOLERANCE_M = 0.01
MIN_FLIGHT_M = 1.5
BALL_TOLERANCE_M = 0.05


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


def _shot_event_id(session: MatchSession, period: int, at: float) -> str:
    return next(e.event_id for e in session.result.events
                if e.period == period and abs(e.match_second - at) <= LINE_TOLERANCE_M and e.event_type.value == "shot")


def test_the_77th_minute_winner_matches_the_measured_analysis(session: MatchSession) -> None:
    story = session.replay(*WINNER)
    analysis = story["analysis"]
    assert isinstance(analysis, dict)
    card = analysis["card"]
    assert card["result"] == "goal" and analysis["xg"] == 0.075 and analysis["goal_chance_pct"] == 8
    assert (card["distance_m"], card["angle_deg"], card["speed_kmh"]) == (10.9, 35.4, 81.8)
    assist = analysis["assist"]
    assert assist["passer_id"] == "kba-09" and assist["length_m"] == 34.4
    assist_id = next(e.event_id for e in session.result.events if e.player_id == "kba-09"
                     and e.receiver_id == "kba-11" and e.event_type.value == "pass" and e.match_second < WINNER[1]
                     and e.period == WINNER[0] and e.match_second > WINNER[1] - REPLAY_MAX_LEAD_S)
    assert assist["xt_added"] == session.threats[assist_id].to_dict()["xt_added"]
    assert analysis["build_up"]["passes"] == 6 and analysis["build_up"]["duration_s"] == 31.4
    assert analysis["keeper_in_cone"] is True and analysis["defenders_in_cone"] == 0


def test_the_15th_minute_opener_matches_the_measured_analysis(session: MatchSession) -> None:
    analysis = session.replay(*OPENER)["analysis"]
    assert isinstance(analysis, dict)
    assert analysis["card"]["result"] == "goal" and analysis["card"]["distance_m"] == 2.0
    assert analysis["assist"]["passer_id"] == "irv-09" and analysis["build_up"]["passes"] == 5


@pytest.mark.parametrize("period, at", [WINNER, OPENER])
def test_goal_replays_keep_the_keyframe_invariants(session: MatchSession, period: int, at: float) -> None:
    frames = session.replay(period, at)["frames"]
    assert isinstance(frames, list)
    build_up = [f for f in frames if f["phase"] == "build_up"]
    shot = next(f for f in frames if f["phase"] == "shot")
    assert build_up and all(f["match_second"] >= at - REPLAY_MAX_LEAD_S for f in build_up)
    event = next(e for e in session.result.events if e.event_id == _shot_event_id(session, period, at))
    assert event.start is not None and event.team_id is not None
    origin = event.start if event.team_id == session.result.metadata.home.team_id else Point(
        105.0 - event.start.x, 68.0 - event.start.y)
    assert distance(Point(*shot["ball"]), origin) <= BALL_TOLERANCE_M
    last = frames[-1]
    assert last["phase"] == "flight"
    assert min(abs(last["ball"][0] - line) for line in GOAL_LINES) <= LINE_TOLERANCE_M
    assert distance(Point(*last["ball"]), Point(*shot["ball"])) >= MIN_FLIGHT_M
    times = [f["match_second"] for f in frames]
    assert times == sorted(times)


def test_a_second_without_a_shot_has_no_replay(session: MatchSession) -> None:
    with pytest.raises(ReplayNotFoundError):
        session.replay(WINNER[0], WINNER[1] + 5)
