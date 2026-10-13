"""Tests for the per-client rate limit on starting matches.

Requests go through the real app with an offline model, identifying clients by the X-Forwarded-For header.
They check the limit, that clients have separate budgets, and that a forged leading header entry does not evade it.
"""

from test_api import _client

from insidegame.live.registry import CREATE_MAX_PER_WINDOW

HTTP_CREATED = 201
HTTP_TOO_MANY = 429
CLIENT_A = "203.0.113.10"
CLIENT_B = "203.0.113.20"


def _start(client, forwarded_for: str) -> int:  # noqa: ANN001
    return client.post("/api/matches", json={}, headers={"X-Forwarded-For": forwarded_for}).status_code


def test_each_client_may_start_a_limited_number_of_matches_per_window() -> None:
    with _client() as client:
        assert [_start(client, CLIENT_A) for _ in range(CREATE_MAX_PER_WINDOW)] == [HTTP_CREATED] * CREATE_MAX_PER_WINDOW
        response = client.post("/api/matches", json={}, headers={"X-Forwarded-For": CLIENT_A})
        assert response.status_code == HTTP_TOO_MANY and "retry in" in response.json()["detail"]
        assert _start(client, CLIENT_B) == HTTP_CREATED


def test_a_forged_leading_forwarded_entry_does_not_reset_the_budget() -> None:
    with _client() as client:
        for _ in range(CREATE_MAX_PER_WINDOW):
            _start(client, CLIENT_A)
        assert _start(client, f"198.51.100.7, {CLIENT_A}") == HTTP_TOO_MANY
