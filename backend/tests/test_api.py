"""HTTP API tests using the offline model runtime and an instant replay sleeper.

They cover health, metadata, session creation and lookup, error mapping, and a full server-sent event stream.
No model server is required.
"""

import asyncio

from agent_framework.openai import OpenAIChatCompletionClient
from fastapi.testclient import TestClient

from insidegame.adapters.model_client import ModelProvider, ModelRuntime
from insidegame.agents.runner import RunPolicy
from insidegame.api.app import create_app

PERSONA_COUNT = 5


async def _instant(seconds: float) -> None:
    await asyncio.sleep(0)


def _client() -> TestClient:
    runtime = ModelRuntime(ModelProvider.OFFLINE,
                           OpenAIChatCompletionClient(model="unused", base_url="http://127.0.0.1:9", api_key="x"),
                           RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix=""))
    return TestClient(create_app(runtime, _instant))


def test_health_and_metadata() -> None:
    with _client() as client:
        assert client.get("/health").json() == {"status": "ok", "model_provider": "offline", "sessions": 0}
        assert len(client.get("/personas").json()) == PERSONA_COUNT
        assert {c["key"] for c in client.get("/clubs").json()} >= {"brookhaven", "ironvale"}
        assert client.get("/diagnostics").json()["model_reachable"] is None


def test_errors_map_to_http_status() -> None:
    with _client() as client:
        assert client.post("/matches", json={"home": "nowhere"}).status_code == 400
        assert client.get("/matches/missing").status_code == 404
        created = client.post("/matches", json={}).json()
        bad = client.get(f"/matches/{created['session_id']}/stream", params={"persona": "superfan"})
        assert bad.status_code == 400


def test_stream_delivers_full_match() -> None:
    with _client() as client:
        session_id = client.post("/matches", json={"home": "brookhaven", "away": "silverlake", "seed": 3}).json()[
            "session_id"]
        names = []
        with client.stream("GET", f"/matches/{session_id}/stream", params={"persona": "newcomer", "language": "es"}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            for line in r.iter_lines():
                if line.startswith("event: "):
                    names.append(line.removeprefix("event: "))
                    if names[-1] == "end":
                        break
        assert names[0] == "match" and names[-1] == "end"
        assert "cue" in names and names.count("recap") == 2
        detail = client.get(f"/matches/{session_id}").json()
        assert detail["status"] == "finished" and len(detail["recaps"]) == 2
