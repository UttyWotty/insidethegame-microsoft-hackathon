"""Tests for the producer console event stream generator.

They check that a summary frame is sent only when the state changes, that heartbeats fill quiet spells, and that
the stream ends with the final state once the session finishes. Time is simulated with an instant sleeper.
"""

import asyncio

from insidegame.api.producer_sse import HEARTBEAT_FRAME, producer_frames


def _collect(states: list[dict[str, object]], heartbeat_s: float = 100.0) -> list[str]:
    calls = {"n": 0}

    def summary() -> dict[str, object]:
        state = states[min(calls["n"], len(states) - 1)]
        calls["n"] += 1
        return state

    def finished() -> bool:
        return calls["n"] >= len(states) - 1

    async def instant(_: float) -> None:
        return None

    async def run() -> list[str]:
        return [f async for f in producer_frames(summary, finished, sample_s=1.0, heartbeat_s=heartbeat_s,
                                                 sleep=instant)]

    return asyncio.run(run())


def test_summary_frames_are_sent_only_on_change_and_the_stream_ends_after_finishing() -> None:
    frames = _collect([{"hold": False}, {"hold": False}, {"hold": True}, {"hold": True}])
    summaries = [f for f in frames if f.startswith("event: summary")]
    assert len(summaries) == 2 and '"hold": true' in summaries[-1]
    assert frames[-1] == "event: end\ndata: {}\n\n"


def test_quiet_spells_get_heartbeats() -> None:
    frames = _collect([{"hold": False}] * 6, heartbeat_s=2.0)
    assert HEARTBEAT_FRAME in frames
