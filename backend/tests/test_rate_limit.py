"""Tests for the sliding-window limiter and its use on the ask endpoint.

Time is passed explicitly to the limiter, so window behaviour is tested without sleeping.
The endpoint test lowers the limit through the registry to keep the run fast.
"""

from test_api import _client

from insidegame.core.rate_limit import SlidingWindowLimiter

WINDOW = 60.0


def test_limiter_allows_up_to_the_limit_then_rejects() -> None:
    limiter = SlidingWindowLimiter(max_events=2, window_s=WINDOW)
    assert limiter.allow("s", 0.0) and limiter.allow("s", 1.0)
    assert not limiter.allow("s", 2.0)
    assert limiter.retry_after("s", 2.0) == WINDOW - 2.0


def test_limiter_frees_capacity_as_the_window_slides_and_isolates_keys() -> None:
    limiter = SlidingWindowLimiter(max_events=1, window_s=WINDOW)
    assert limiter.allow("a", 0.0) and limiter.allow("b", 0.0)
    assert not limiter.allow("a", WINDOW - 1)
    assert limiter.allow("a", WINDOW + 0.1)


def test_ask_endpoint_returns_429_when_over_the_limit() -> None:
    with _client() as client:
        client.app.state.registry.ask_limiter = SlidingWindowLimiter(max_events=1, window_s=WINDOW)  # type: ignore[attr-defined]
        session_id = client.post("/api/matches", json={}).json()["session_id"]
        body = {"question": "Who is on top?"}
        assert client.post(f"/api/matches/{session_id}/ask", json=body).status_code == 200
        limited = client.post(f"/api/matches/{session_id}/ask", json=body)
        assert limited.status_code == 429 and "retry in" in limited.json()["detail"]
