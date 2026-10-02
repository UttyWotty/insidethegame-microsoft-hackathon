"""Server-sent events encoding and the per-subscriber streaming generator.

Each LiveMessage becomes one SSE frame whose event name is the message type and whose data is JSON.
Heartbeat comments keep idle connections open through proxies.
"""

import asyncio
import json
from collections.abc import AsyncIterator

from insidegame.live.session import LiveMessage, MatchSession, MessageType, Subscriber

HEARTBEAT_S: float = 15.0
HEARTBEAT_FRAME: str = ": heartbeat\n\n"


def encode(message: LiveMessage) -> str:
    """Format a message as one SSE frame."""
    return f"event: {message.type.value}\ndata: {json.dumps(message.data, ensure_ascii=False)}\n\n"


async def stream(session: MatchSession, subscriber: Subscriber) -> AsyncIterator[str]:
    """Yield SSE frames for a subscriber until the match ends or the client disconnects."""
    try:
        while True:
            try:
                message = await asyncio.wait_for(subscriber.queue.get(), HEARTBEAT_S)
            except TimeoutError:
                yield HEARTBEAT_FRAME
                continue
            yield encode(message)
            if message.type is MessageType.END:
                return
    finally:
        session.unsubscribe(subscriber)
