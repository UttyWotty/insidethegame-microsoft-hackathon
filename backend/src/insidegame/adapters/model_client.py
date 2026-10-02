"""Builds the chat client and run policy from environment configuration.

Local development targets an MLX (mlx_lm.server) or Ollama server through its OpenAI-compatible endpoint, and deployment targets a
Microsoft Foundry OpenAI-compatible endpoint; both use the same Agent Framework client, so only configuration changes.
The offline provider makes zero model attempts, so every output comes from grounded templates without any server.
"""

import asyncio
import os
from dataclasses import dataclass
from enum import StrEnum

from agent_framework.openai import OpenAIChatCompletionClient

from insidegame.agents.runner import RunPolicy
from insidegame.core.exceptions import ModelConfigError


class ModelProvider(StrEnum):
    """Supported model hosting options."""

    OLLAMA = "ollama"
    MLX = "mlx"
    FOUNDRY = "foundry"
    OFFLINE = "offline"


MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", ModelProvider.MLX.value)
MODEL_NAME: str = os.getenv("MODEL_NAME", "mlx-community/gemma-3-12b-it-4bit")
MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:8766/v1")
MODEL_API_KEY: str = os.getenv("MODEL_API_KEY", "local")
MODEL_TIMEOUT_S: float = float(os.getenv("MODEL_TIMEOUT_S", "45"))
MODEL_MAX_ATTEMPTS: int = int(os.getenv("MODEL_MAX_ATTEMPTS", "2"))
MODEL_PROMPT_SUFFIX: str = os.getenv("MODEL_PROMPT_SUFFIX", "")
MODEL_MAX_CONCURRENCY: str = os.getenv("MODEL_MAX_CONCURRENCY", "")
LOCAL_DEFAULT_CONCURRENCY: int = 1
LOCAL_PROVIDERS: frozenset[ModelProvider] = frozenset({ModelProvider.OLLAMA, ModelProvider.MLX})
INLINE_SCHEMA_PROVIDERS: frozenset[ModelProvider] = frozenset({ModelProvider.MLX})
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
    if provider is ModelProvider.FOUNDRY and MODEL_API_KEY == "local":
        raise ModelConfigError("MODEL_API_KEY must be set for the foundry provider")
    client = OpenAIChatCompletionClient(model=MODEL_NAME, base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)
    suffix = MODEL_PROMPT_SUFFIX if provider in LOCAL_PROVIDERS else ""
    attempts = OFFLINE_MAX_ATTEMPTS if provider is ModelProvider.OFFLINE else MODEL_MAX_ATTEMPTS
    policy = RunPolicy(MODEL_TIMEOUT_S, attempts, suffix, provider in INLINE_SCHEMA_PROVIDERS, _gate(provider))
    return ModelRuntime(provider, client, policy)


def _gate(provider: ModelProvider) -> asyncio.Semaphore | None:
    """Concurrency gate: MODEL_MAX_CONCURRENCY when set (0 means unlimited), else 1 for local servers."""
    if MODEL_MAX_CONCURRENCY:
        limit = int(MODEL_MAX_CONCURRENCY)
        return asyncio.Semaphore(limit) if limit > 0 else None
    return asyncio.Semaphore(LOCAL_DEFAULT_CONCURRENCY) if provider in LOCAL_PROVIDERS else None
