"""Tests for spoken commentary: SSML construction, line lookup, the Azure Speech adapter, and the speech routes.

The adapter runs against an in-process HTTP transport, and routes use a fake synthesizer, so nothing calls Azure.
They check escaping and voices, that only lines the match produced can be voiced, caching, and failure mapping.
"""

import asyncio
import json

import httpx
import pytest
from test_api import _client

from insidegame.adapters.speech_client import OUTPUT_FORMAT, SYNTHESIS_PATH, AzureSpeechClient
from insidegame.api import routes_speech
from insidegame.core.exceptions import LineNotFoundError, SpeechUnavailableError
from insidegame.domain.enums import Intensity
from insidegame.live.spoken_lines import find_spoken_line
from insidegame.speech.ssml import MAX_SPEECH_CHARS, build_ssml, voice_for

ENDPOINT = "https://ais-test.cognitiveservices.azure.com/"
AUDIO = b"ID3-fake-mp3"
HTTP_OK, HTTP_NOT_FOUND, HTTP_TOO_MANY, HTTP_UNAVAILABLE, HTTP_UNAUTHORIZED = 200, 404, 429, 503, 401


async def _token() -> str:
    return "entra-token"


def test_ssml_uses_the_language_voice_and_escapes_and_caps_text() -> None:
    voice = voice_for("ES")
    assert voice == "es-ES-AlvaroNeural" and voice_for("xx") is None
    ssml = build_ssml("Goal <now> & " + "x" * MAX_SPEECH_CHARS, voice)
    assert 'xml:lang="es-ES"' in ssml and f'name="{voice}"' in ssml
    assert "&lt;now&gt; &amp;" in ssml and "<now>" not in ssml
    assert ssml.count("x") <= MAX_SPEECH_CHARS
    assert 'rate="+8%" pitch="+0%"' in ssml
    assert 'rate="+22%" pitch="+15%"' in build_ssml("GOAL!", voice, Intensity.PEAK)


def test_only_lines_the_session_produced_can_be_found() -> None:
    commentary = [{"line_id": "e9-pbp", "text": "Kick-off!", "intensity": "normal"}]
    cues = {"casual-es-none-none": [{"moment_id": "m3", "commentary": "¡Gol!", "commentary_language": "es",
                                     "commentary_intensity": "peak"}]}
    assert find_spoken_line("e9-pbp", None, commentary, cues) == ("Kick-off!", "en", Intensity.NORMAL)
    assert find_spoken_line("moment-m3", "casual-es-none-none", commentary, cues) == ("¡Gol!", "es", Intensity.PEAK)
    for ref, segment in (("anything", None), ("moment-m3", "analyst-en-none-none"), ("moment-m4", "casual-es-none-none")):
        with pytest.raises(LineNotFoundError):
            find_spoken_line(ref, segment, commentary, cues)


def _adapter(status: int, seen: list[httpx.Request]) -> AzureSpeechClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=AUDIO)
    return AzureSpeechClient(ENDPOINT, _token, httpx.AsyncClient(transport=httpx.MockTransport(handle)))


def test_adapter_posts_ssml_with_an_entra_token_and_caches_repeated_lines() -> None:
    seen: list[httpx.Request] = []
    client = _adapter(HTTP_OK, seen)
    first = asyncio.run(client.synthesize("What a goal!", "en"))
    second = asyncio.run(client.synthesize("What a goal!", "en"))
    assert first == second == AUDIO and len(seen) == 1
    request = seen[0]
    assert str(request.url) == ENDPOINT + SYNTHESIS_PATH
    assert request.headers["Authorization"] == "Bearer entra-token"
    assert request.headers["X-Microsoft-OutputFormat"] == OUTPUT_FORMAT
    assert "en-GB-RyanNeural" in request.content.decode()


def test_adapter_failures_and_unsupported_languages_raise_speech_unavailable() -> None:
    with pytest.raises(SpeechUnavailableError):
        asyncio.run(_adapter(HTTP_UNAUTHORIZED, []).synthesize("Hello", "en"))
    with pytest.raises(SpeechUnavailableError):
        asyncio.run(_adapter(HTTP_OK, []).synthesize("Hello", "xx"))


class _FakeSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def synthesize(self, text: str, language: str, intensity: Intensity) -> bytes:
        self.calls.append((text, language))
        return AUDIO


def _finished_match(client) -> tuple[str, str]:  # noqa: ANN001
    session_id = client.post("/api/matches", json={"seed": 3}).json()["session_id"]
    last_line, event = "", ""
    with client.stream("GET", f"/api/matches/{session_id}/stream", params={"persona": "analyst"}) as response:
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: ") and event == "commentary":
                last_line = json.loads(line.removeprefix("data: "))["line_id"]
    return session_id, last_line


def test_speech_routes_voice_match_lines_and_report_availability() -> None:
    fake = _FakeSpeech()
    with _client(speech_factory=lambda: fake) as client:
        assert client.get("/api/speech/status").json() == {"available": True}
        session_id, line_id = _finished_match(client)
        audio = client.get(f"/api/matches/{session_id}/speech", params={"ref": line_id})
        assert audio.status_code == HTTP_OK and audio.content == AUDIO
        assert audio.headers["content-type"] == "audio/mpeg" and fake.calls[0][1] == "en"
        assert client.get(f"/api/matches/{session_id}/speech", params={"ref": "invented"}).status_code == HTTP_NOT_FOUND


def test_speech_is_unavailable_without_a_configured_service() -> None:
    with _client() as client:
        assert client.get("/api/speech/status").json() == {"available": False}
        session_id = client.post("/api/matches", json={}).json()["session_id"]
        response = client.get(f"/api/matches/{session_id}/speech", params={"ref": "x"})
        assert response.status_code == HTTP_UNAVAILABLE


def test_speech_requests_are_rate_limited_per_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes_speech, "SPEECH_MAX_PER_WINDOW", 1)
    with _client(speech_factory=_FakeSpeech) as client:
        session_id, line_id = _finished_match(client)
        url = f"/api/matches/{session_id}/speech"
        assert client.get(url, params={"ref": line_id}).status_code == HTTP_OK
        assert client.get(url, params={"ref": line_id}).status_code == HTTP_TOO_MANY
