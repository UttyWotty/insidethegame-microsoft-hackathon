"""Tests for the MCP server: tool calls against live sessions, the HTTP transport, and the bearer guard.

Tool calls go through the server's public call_tool interface; the transport test speaks real JSON-RPC over HTTP.
The offline runtime keeps every call model-free.
"""

import asyncio
import json

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient as StarletteClient
from test_api import _client

from insidegame.api.mcp_auth import BearerTokenGuard

MCP_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
EXPECTED_TOOLS = {"list_clubs", "start_match", "list_matches", "get_match_state", "get_key_moments",
                  "get_player_stats", "get_recaps", "ask_match_companion", "get_threat_leaderboard", "get_team_shape"}


def _structured(result: object) -> object:
    content = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if content is not None:
        return content.get("result", content) if isinstance(content, dict) else content
    return json.loads(result.content[0].text)  # type: ignore[attr-defined]


def test_tools_drive_a_live_session_end_to_end() -> None:
    with _client() as client:
        mcp = client.app.state.mcp  # type: ignore[attr-defined]

        async def scenario() -> tuple[object, object, object, object]:
            started = _structured(await mcp.call_tool("start_match", {"home": "brookhaven", "away": "silverlake", "seed": 3}))
            session_id = started["session_id"]  # type: ignore[index]
            await asyncio.sleep(0.5)
            state = _structured(await mcp.call_tool("get_match_state", {"session_id": session_id}))
            moments = _structured(await mcp.call_tool("get_key_moments", {"session_id": session_id, "limit": 3}))
            answer = _structured(await mcp.call_tool("ask_match_companion",
                                                     {"session_id": session_id, "question": "Who is on top?"}))
            return started, state, moments, answer

        started, state, moments, answer = client.portal.call(scenario)  # type: ignore[union-attr]
        assert started["status"] in {"pending", "live", "finished"}  # type: ignore[index]
        assert "Brookhaven FC" in state["score"]  # type: ignore[index]
        assert isinstance(moments, list) and len(moments) <= 3
        assert answer["source"] == "fallback" and answer["answer"]  # type: ignore[index]


def test_http_transport_lists_all_tools() -> None:
    with _client() as client:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "1"}}}
        assert client.post("/mcp/", json=init, headers=MCP_HEADERS).status_code == 200
        listed = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=MCP_HEADERS)
        names = {tool["name"] for tool in listed.json()["result"]["tools"]}
        assert EXPECTED_TOOLS <= names


def test_bearer_guard_rejects_missing_or_wrong_token() -> None:
    inner = Starlette(routes=[Route("/", lambda request: PlainTextResponse("ok"))])
    guarded = StarletteClient(BearerTokenGuard(inner, "secret"))
    assert guarded.get("/").status_code == 401
    assert guarded.get("/", headers={"authorization": "Bearer wrong"}).status_code == 401
    assert guarded.get("/", headers={"authorization": "Bearer secret"}).text == "ok"
    assert StarletteClient(BearerTokenGuard(inner, "")).get("/").text == "ok"


def _initialise(client: object) -> None:
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
    assert client.post("/mcp/", json=init, headers=MCP_HEADERS).status_code == 200  # type: ignore[attr-defined]


def test_threat_leaderboard_ranks_teams_and_players_of_a_live_session() -> None:
    with _client() as client:
        mcp = client.app.state.mcp  # type: ignore[attr-defined]

        async def scenario() -> tuple[object, object]:
            started = _structured(await mcp.call_tool("start_match", {"home": "kestrel_bay", "away": "ironvale", "seed": 7}))
            session_id = started["session_id"]  # type: ignore[index]
            await asyncio.sleep(0.5)
            board = _structured(await mcp.call_tool("get_threat_leaderboard", {"session_id": session_id, "limit": 3}))
            stats = _structured(await mcp.call_tool("get_player_stats",
                                                    {"session_id": session_id, "player_name": board["players"][0]["name"]}))  # type: ignore[index]
            return board, stats

        board, stats = client.portal.call(scenario)  # type: ignore[union-attr]
        assert [t["team_id"] for t in board["teams"]] == ["kba", "irv"]  # type: ignore[index]
        assert all({"team_id", "name", "xt_added", "line_breaking_passes"} == set(t) for t in board["teams"])  # type: ignore[index]
        players = board["players"]  # type: ignore[index]
        assert 0 < len(players) <= 3 and all(p["xt_added"] > 0 for p in players)
        assert [p["xt_added"] for p in players] == sorted((p["xt_added"] for p in players), reverse=True)
        assert stats["xt_added"] == players[0]["xt_added"] and "line_breaking_passes" in stats  # type: ignore[index]


def test_threat_leaderboard_for_an_unknown_session_is_an_mcp_error_result() -> None:
    with _client() as client:
        _initialise(client)
        call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "get_threat_leaderboard", "arguments": {"session_id": "missing"}}}
        response = client.post("/mcp/", json=call, headers=MCP_HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["result"]["isError"] is True
        assert client.get("/api/health").json()["status"] == "ok"


def test_threat_leaderboard_rejects_a_limit_outside_one_to_twenty_two() -> None:
    with _client() as client:
        _initialise(client)
        for limit in (0, 23, -1):
            call = {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": "get_threat_leaderboard", "arguments": {"session_id": "missing", "limit": limit}}}
            body = client.post("/mcp/", json=call, headers=MCP_HEADERS).json()
            assert body["result"]["isError"] is True
            assert "validation error" in body["result"]["content"][0]["text"]


def test_team_shape_tool_reports_readings_and_shifts_of_a_live_session() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "kestrel_bay", "away": "ironvale", "seed": 201}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "analyst"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        mcp = client.app.state.mcp  # type: ignore[attr-defined]

        async def scenario() -> object:
            return _structured(await mcp.call_tool("get_team_shape", {"session_id": session_id}))

        shape = client.portal.call(scenario)  # type: ignore[union-attr]
        assert set(shape) == {"home", "away", "shifts"}  # type: ignore[arg-type]
        assert shape["home"]["block"] in {"high", "mid", "low"}  # type: ignore[index]
        assert shape["away"]["team_id"] == "irv"  # type: ignore[index]
        shifts = shape["shifts"]  # type: ignore[index]
        assert 0 < len(shifts) <= 5 and all(s["kind"] == "shape_shift" and "line_before_m" in s["facts"] for s in shifts)


def test_team_shape_for_an_unknown_session_is_an_mcp_error_result() -> None:
    with _client() as client:
        _initialise(client)
        call = {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "get_team_shape", "arguments": {"session_id": "missing"}}}
        body = client.post("/mcp/", json=call, headers=MCP_HEADERS).json()
        assert body["result"]["isError"] is True
        assert client.get("/api/health").json()["status"] == "ok"
