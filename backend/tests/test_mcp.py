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
                  "get_player_stats", "get_recaps", "ask_match_companion"}


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
