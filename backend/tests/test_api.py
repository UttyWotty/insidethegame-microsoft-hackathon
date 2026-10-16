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


def test_producer_stream_sends_the_final_summary_then_ends_for_a_finished_match() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "brookhaven", "away": "silverlake", "seed": 3}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "casual"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        with client.stream("GET", f"/api/matches/{session_id}/producer/stream") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            lines = [line for line in r.iter_lines() if line]
        assert lines[0] == "event: summary" and lines[-2] == "event: end"
        assert '"timeline"' in lines[1]


def test_highlights_wait_for_the_recap_then_replay_key_moments() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "kestrel_bay", "away": "ironvale", "seed": 7}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "casual"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        reel = client.get(f"/api/matches/{session_id}/highlights", params={"stage": "full_time"}).json()
        assert reel["stage"] == "full_time" and reel["headline"].startswith("Full-time")
        assert reel["clips"] and all(clip["frames"] and clip["commentary"] for clip in reel["clips"])
        assert len(reel["clips"][0]["frames"][0]["positions"]) == 22
        assert client.get(f"/api/matches/{session_id}/highlights", params={"stage": "extra"}).status_code == 422
        goal = next(c for c in reel["clips"] if c["kind"] == "goal")
        replay = client.get(f"/api/matches/{session_id}/replay",
                            params={"period": goal["period"], "at": goal["match_second"]}).json()
        assert replay["frames"] and all(f["period"] == goal["period"] for f in replay["frames"])
        assert client.get(f"/api/matches/{session_id}/replay", params={"period": 3, "at": 1}).status_code == 422


def test_studio_returns_maps_control_and_the_analyst_pick() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "kestrel_bay", "away": "ironvale", "seed": 7}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "analyst"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        studio = client.get(f"/api/matches/{session_id}/studio", params={"window": "last_15"}).json()
        assert studio["window"] == "last_15" and studio["events"] > 0
        assert studio["teams"]["home"]["network"]["nodes"] and len(studio["teams"]["away"]["heat"]) == 8
        assert 0 < studio["control"]["home_share"] < 100 and studio["analyst"]["theme"]
        assert studio["recommended"] in {"heat_map", "pressing", "pass_network", "space_control"}


def test_producer_traces_every_agent_of_a_produced_moment() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "kestrel_bay", "away": "ironvale", "seed": 7}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "analyst"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        traces = client.get(f"/api/matches/{session_id}/producer").json()["traces"]
        assert traces and traces[0]["finished"]
        agents = [step["agent"] for step in traces[0]["steps"]]
        assert agents[0] == "Intake" and agents[-1] == "Broadcast Translator" and len(agents) == 6
        assert all(step["status"] == "done" and step["note"] for step in traces[0]["steps"])


def test_match_detail_snapshot_carries_the_threat_leaders() -> None:
    with _client() as client:
        session_id = client.post("/api/matches", json={"home": "kestrel_bay", "away": "ironvale", "seed": 7}).json()[
            "session_id"]
        with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "analyst"}) as r:
            for line in r.iter_lines():
                if line == "event: end":
                    break
        snapshot = client.get(f"/api/matches/{session_id}").json()["snapshot"]
        leaders = snapshot["threat_leaders"]
        assert 0 < len(leaders) <= 5 and all(leader["xt_added"] > 0 for leader in leaders)
        assert snapshot["home"]["stats"]["line_breaking_passes"] > 0
