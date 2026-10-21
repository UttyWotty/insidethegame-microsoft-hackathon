"""End-to-end tests of instant replay stories on the demo fixture (DEMO_SEED), run through a real MatchSession.

The session uses the offline agent policy and an instant sleeper, so the full match plays in seconds while the
stored frames and threats come from the same interpretation code the broadcast runs.
They pin the measured numbers of the 28' and 65' goals and the keyframe invariants every shot replay must keep.
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
from insidegame.simulation.roster import DEMO_SEED, build_fixture

OFFLINE_POLICY = RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix="")
SPEED = 30.0
WINNER = (2, 3841.21)
OPENER = (1, 1651.62)
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


def test_the_65th_minute_winner_matches_the_measured_analysis(session: MatchSession) -> None:
    story = session.replay(*WINNER)
    analysis = story["analysis"]
    assert isinstance(analysis, dict)
    card = analysis["card"]
    assert card["result"] == "goal" and analysis["xg"] == 0.136 and analysis["goal_chance_pct"] == 14
    assert (card["distance_m"], card["angle_deg"], card["speed_kmh"]) == (9.4, 41.5, 107.3)
    assist = analysis["assist"]
    assert assist["passer_id"] == "kba-07" and assist["length_m"] == 26.2
    assist_id = next(e.event_id for e in reversed(session.result.events) if e.player_id == "kba-07"
                     and e.receiver_id == "kba-09" and e.event_type.value == "pass" and e.match_second < WINNER[1]
                     and e.period == WINNER[0])
    assert assist["xt_added"] == session.threats[assist_id].to_dict()["xt_added"]
    assert analysis["build_up"]["passes"] == 7 and analysis["build_up"]["duration_s"] == 35.9
    assert analysis["keeper_in_cone"] is True and analysis["defenders_in_cone"] == 0


def test_the_28th_minute_opener_matches_the_measured_analysis(session: MatchSession) -> None:
    analysis = session.replay(*OPENER)["analysis"]
    assert isinstance(analysis, dict)
    assert analysis["card"]["result"] == "goal" and analysis["card"]["distance_m"] == 4.6
    assert analysis["assist"]["passer_id"] == "kba-10" and analysis["build_up"]["passes"] == 7


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


KEEPER_CHECK_RANGE_M = 20.0
GOAL_CENTER_Y = 34.0
REPLAYED_RESULTS = {"goal", "saved"}


def test_close_goal_and_save_replays_show_the_keeper_between_the_strike_and_the_goal(session: MatchSession) -> None:
    metadata = session.result.metadata
    checked = 0
    for event in session.result.events:
        if event.event_type.value != "shot" or event.shot_result is None or event.shot_result.value not in REPLAYED_RESULTS:
            continue
        frames = session.replay(event.period, round(event.match_second, 2))["frames"]
        shot = next(f for f in frames if f["phase"] == "shot")
        attacking_home = event.team_id == metadata.home.team_id
        goal_x = GOAL_LINES[1] if attacking_home else GOAL_LINES[0]
        ball_x, ball_y = shot["ball"]
        if distance(Point(ball_x, ball_y), Point(goal_x, GOAL_CENTER_Y)) > KEEPER_CHECK_RANGE_M:
            continue
        keeper_id = (metadata.away if attacking_home else metadata.home).goalkeeper().player_id
        keeper_x = next(x for pid, x, _ in shot["positions"] if pid == keeper_id)
        low, high = sorted((ball_x, goal_x))
        assert low < keeper_x < high, (event.event_id, shot["ball"], keeper_x)
        checked += 1
    assert checked
