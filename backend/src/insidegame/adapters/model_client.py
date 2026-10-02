"""Builds the chat client and run policy from environment configuration.

Local development targets an Ollama server through its OpenAI-compatible endpoint, and deployment targets a
Microsoft Foundry OpenAI-compatible endpoint; both use the same Agent Framework client, so only configuration changes.
The offline provider makes zero model attempts, so every output comes from grounded templates without any server.
"""

import os
from dataclasses import dataclass
from enum import StrEnum

from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.runner import RunPolicy
from insidegame.core.exceptions import ModelConfigError


class ModelProvider(StrEnum):
    """Supported model hosting options."""

    OLLAMA = "ollama"
    FOUNDRY = "foundry"
    OFFLINE = "offline"


MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", ModelProvider.OLLAMA.value)
MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3:8b")
MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "http://localhost:11434/v1")
MODEL_API_KEY: str = os.getenv("MODEL_API_KEY", "ollama")
MODEL_TIMEOUT_S: float = float(os.getenv("MODEL_TIMEOUT_S", "45"))
MODEL_MAX_ATTEMPTS: int = int(os.getenv("MODEL_MAX_ATTEMPTS", "2"))
MODEL_PROMPT_SUFFIX: str = os.getenv("MODEL_PROMPT_SUFFIX", "/no_think")
OFFLINE_MAX_ATTEMPTS: int = 0


@dataclass(frozen=True)
class ModelRuntime:
    """A configured chat client together with its execution policy."""

    provider: ModelProvider
    client: OpenAIChatCompletionClient
    policy: RunPolicy


def build_model_runtime() -> ModelRuntime:
    """Create the chat client and run policy described by the environment."""
    try:
        provider = ModelProvider(MODEL_PROVIDER)
    except ValueError as exc:
        raise ModelConfigError(f"Unknown MODEL_PROVIDER {MODEL_PROVIDER!r}") from exc
    if provider is ModelProvider.FOUNDRY and MODEL_API_KEY == "ollama":
        raise ModelConfigError("MODEL_API_KEY must be set for the foundry provider")
    client = OpenAIChatCompletionClient(model=MODEL_NAME, base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)
    suffix = MODEL_PROMPT_SUFFIX if provider is ModelProvider.OLLAMA else ""
    attempts = OFFLINE_MAX_ATTEMPTS if provider is ModelProvider.OFFLINE else MODEL_MAX_ATTEMPTS
    return ModelRuntime(provider, client, RunPolicy(MODEL_TIMEOUT_S, attempts, suffix))
