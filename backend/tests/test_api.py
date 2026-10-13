"""HTTP API tests using the offline model runtime and an instant replay sleeper.

They cover health, metadata, session creation and lookup, error mapping, and a full server-sent event stream.
No model server is required.
"""

import asyncio

from agent_framework.openai import OpenAIChatCompletionClient
from fastapi.testclient import TestClient

from insidegame.adapters.model_client import ModelProvider, ModelRuntime
from insidegame.agents.runner import RunPolicy
from insidegame.api.app import SpeechFactory, create_app

PERSONA_COUNT = 5


async def _instant(seconds: float) -> None:
    await asyncio.sleep(0)


def _no_speech() -> None:
    return None


def _client(static_dir: str = "", speech_factory: SpeechFactory = _no_speech) -> TestClient:
    runtime = ModelRuntime(ModelProvider.OFFLINE,
                           OpenAIChatCompletionClient(model="unused", base_url="http://127.0.0.1:9", api_key="x"),
                           RunPolicy(timeout_s=1.0, max_attempts=0, prompt_suffix=""))
    return TestClient(create_app(runtime, _instant, static_dir, speech_factory))


def test_health_and_metadata() -> None:
    with _client() as client:
        assert client.get("/api/health").json() == {"status": "ok", "model_provider": "offline", "sessions": 0}
        assert len(client.get("/api/personas").json()) == PERSONA_COUNT
        assert {c["key"] for c in client.get("/api/clubs").json()} >= {"brookhaven", "ironvale"}
        assert client.get("/api/diagnostics").json()["model_reachable"] is None


def test_errors_map_to_http_status() -> None:
    with _client() as client:
        assert client.post("/api/matches", json={"home": "nowhere"}).status_code == 400
        assert client.get("/api/matches/missing").status_code == 404
        created = client.post("/api/matches", json={}).json()
        bad = client.get(f"/api/matches/{created['session_id']}/stream", params={"persona": "superfan"})
        assert bad.status_code == 400
        unknown = client.get(f"/api/matches/{created['session_id']}/stream",
                             params={"persona": "player_tracker", "player": "ghost-99"})
        assert unknown.status_code == 400


def test_stream_delivers_full_match() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "brookhaven", "away": "silverlake", "seed": 3}).json()[
            "session_id"]
        names = []
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "newcomer", "language": "es"}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            for line in r.iter_lines():
                if line.startswith("event: "):
                    names.append(line.removeprefix("event: "))
                    if names[-1] == "end":
                        break
        assert names[0] == "match" and names[-1] == "end"
        assert "cue" in names and names.count("recap") == 2
        detail = client.get(f"/api/matches/{session_id}").json()
        assert detail["status"] == "finished" and len(detail["recaps"]) == 2


def test_built_frontend_is_served_at_root_alongside_the_api(tmp_path) -> None:  # noqa: ANN001
    (tmp_path / "index.html").write_text("<title>Inside the Game</title>", encoding="utf-8")
    with _client(str(tmp_path)) as client:
        assert "Inside the Game" in client.get("/").text
        assert client.get("/api/health").json()["status"] == "ok"
