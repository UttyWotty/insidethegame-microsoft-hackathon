"""Server-sent event stream of the producer console state, pushed only when it changes.

The generator samples the session's producer summary every SAMPLE_S seconds and emits a summary frame whenever the
serialised state differs from the last one sent, with heartbeat comments while nothing changes. It sends a final
summary and an end frame once the session has finished, so the console stops listening by itself.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

SAMPLE_S: float = 0.5
HEARTBEAT_S: float = 15.0
HEARTBEAT_FRAME: str = ": heartbeat\n\n"
SUMMARY_EVENT: str = "summary"
END_EVENT: str = "end"

Sleeper = Callable[[float], Awaitable[None]]


def frame(event: str, payload: str) -> str:
    """Format one SSE frame from an event name and an already serialised JSON payload."""
    return f"event: {event}\ndata: {payload}\n\n"


async def producer_frames(summary: Callable[[], dict[str, object]], finished: Callable[[], bool],
                          sample_s: float = SAMPLE_S, heartbeat_s: float = HEARTBEAT_S,
                          sleep: Sleeper = asyncio.sleep) -> AsyncIterator[str]:
    """Yield summary frames on change until finished() is true, then a final summary and an end frame.

    Defaults: sample_s is SAMPLE_S (0.5 s between samples) and heartbeat_s is HEARTBEAT_S (15 s of silence before a
    heartbeat comment); sleep is asyncio.sleep, injectable so tests need no real time.
    """
    last = ""
    quiet_s = 0.0
    while True:
        done = finished()
        payload = json.dumps(summary(), ensure_ascii=False, sort_keys=True)
        if payload != last:
            last, quiet_s = payload, 0.0
            yield frame(SUMMARY_EVENT, payload)
        elif quiet_s >= heartbeat_s:
            quiet_s = 0.0
            yield HEARTBEAT_FRAME
        if done:
            yield frame(END_EVENT, "{}")
            return
        await sleep(sample_s)
        quiet_s += sample_s
