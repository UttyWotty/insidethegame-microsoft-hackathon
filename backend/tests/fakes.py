"""Deterministic fake chat client for testing agents without any model server.

Responses are scripted per agent, keyed by a distinctive phrase from that agent's instructions.
The client records every request so tests can assert on prompts and options.
"""

import asyncio
from collections.abc import Sequence
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Message

DELAY_NONE_S: float = 0.0


class ScriptedChatClient(BaseChatClient):
    """Returns queued text responses, chosen by matching the agent's instructions."""

    def __init__(self, scripts: dict[str, list[str]], delay_s: float = DELAY_NONE_S) -> None:
        super().__init__()
        self.scripts = {key: list(values) for key, values in scripts.items()}
        self.delay_s = delay_s
        self.requests: list[tuple[str, Sequence[Message], dict[str, Any]]] = []

    def _inner_get_response(self, *, messages: Sequence[Message], stream: bool, options: dict[str, Any],
                            **kwargs: Any) -> Any:
        instructions = str(options.get("instructions", ""))
        key = next(k for k in self.scripts if k in instructions)
        self.requests.append((key, messages, dict(options)))

        async def respond() -> ChatResponse:
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            text = self.scripts[key].pop(0)
            return ChatResponse(messages=[Message(role="assistant", contents=[text])])

        return respond()
