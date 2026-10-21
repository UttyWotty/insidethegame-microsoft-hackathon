"""Tests that the facts quoted in docs/SUBMISSION.md and the DEMO_SCRIPT replay note match the code.

The submission's agent names and count must equal the agent suite, and its MCP tool names the tools the server lists.
The demo script's note that the 34' replay queues behind the 28' one is checked against the replay queue model.
"""

import re
from dataclasses import fields
from pathlib import Path

from test_api import _client

from insidegame.agents.factory import AgentSuite, create_agent_suite
from insidegame.datasets.demo_story import DEMO_SPEED, REPLAY_DELAY_S, REPLAY_ROLL_S, stream_times
from insidegame.domain.enums import EventType, ShotResult
from insidegame.simulation.engine import simulate_match
from insidegame.simulation.roster import DEMO_AWAY, DEMO_HOME, DEMO_SEED, build_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBMISSION = REPO_ROOT / "docs" / "SUBMISSION.md"
DEMO_SCRIPT = REPO_ROOT / "docs" / "DEMO_SCRIPT.md"
NUMBER_WORDS = {8: "eight", 10: "ten"}
AGENT_LIST = re.compile(r"\*\*Microsoft Agent Framework:\*\* (\w+) agents \(([^)]+)\)")
TOOL_LIST = re.compile(r"MCP server with (\w+) tools \(([^)]+)\)")
MCP_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
QUEUE_NOTE = "the 34' replay now waits in the replay queue and follows the 28' one"
SECONDS_PER_MINUTE = 60


class _NoClient:
    """Stand-in chat client: building the suite only needs an object to hold."""


def _submission() -> str:
    return " ".join(SUBMISSION.read_text(encoding="utf-8").split())


def test_submission_names_every_agent_in_the_suite() -> None:
    found = AGENT_LIST.search(_submission())
    assert found is not None
    suite = create_agent_suite(_NoClient())  # type: ignore[arg-type]
    names = {getattr(suite, f.name).name.replace("_", " ").title() for f in fields(AgentSuite)}
    listed = {name.strip() for name in found.group(2).split(",")}
    assert listed == names
    assert found.group(1) == NUMBER_WORDS[len(names)]


def test_submission_lists_exactly_the_mcp_server_tools() -> None:
    found = TOOL_LIST.search(_submission())
    assert found is not None
    with _client() as client:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "1"}}}
        assert client.post("/mcp/", json=init, headers=MCP_HEADERS).status_code == 200
        listed = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=MCP_HEADERS)
        served = {tool["name"] for tool in listed.json()["result"]["tools"]}
    quoted = set(re.findall(r"`(\w+)`", found.group(2)))
    assert quoted == served
    assert found.group(1) == NUMBER_WORDS[len(served)]


def test_demo_script_queue_note_holds_for_the_demo_match() -> None:
    assert QUEUE_NOTE in " ".join(DEMO_SCRIPT.read_text(encoding="utf-8").split())
    events = simulate_match(build_fixture(DEMO_HOME, DEMO_AWAY, DEMO_SEED)).events
    times = stream_times([(e.period, e.match_second) for e in events])
    goals = {int(e.match_second // SECONDS_PER_MINUTE) + 1: t for e, t in zip(events, times, strict=True)
             if e.event_type is EventType.SHOT and e.shot_result is ShotResult.GOAL}
    first_due = goals[28] + REPLAY_DELAY_S * DEMO_SPEED
    second_due = goals[34] + REPLAY_DELAY_S * DEMO_SPEED
    assert first_due < second_due < first_due + REPLAY_ROLL_S * DEMO_SPEED
