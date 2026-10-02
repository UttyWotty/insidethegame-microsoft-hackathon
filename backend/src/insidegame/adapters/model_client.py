"""Builds the chat client and run policy from environment configuration.

Local development targets an MLX (mlx_lm.server) or Ollama server through its OpenAI-compatible endpoint, and deployment
targets a Microsoft Foundry model deployment with keyless managed identity auth; the same Agent Framework client serves both.
The offline provider makes zero model attempts, so every output comes from grounded templates without any server.
"""

import asyncio
import os
from dataclasses import dataclass
from enum import StrEnum

from agent_framework.openai import OpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential

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
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
LOCAL_API_KEY: str = "local"


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
    client = _foundry_client() if provider is ModelProvider.FOUNDRY else OpenAIChatCompletionClient(
        model=MODEL_NAME, base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)
    suffix = MODEL_PROMPT_SUFFIX if provider in LOCAL_PROVIDERS else ""
    attempts = OFFLINE_MAX_ATTEMPTS if provider is ModelProvider.OFFLINE else MODEL_MAX_ATTEMPTS
    policy = RunPolicy(MODEL_TIMEOUT_S, attempts, suffix, provider in INLINE_SCHEMA_PROVIDERS, _gate(provider))
    return ModelRuntime(provider, client, policy)


def _foundry_client() -> OpenAIChatCompletionClient:
    """Foundry model deployment client: managed identity by default, API key only when one is configured."""
    if not AZURE_OPENAI_ENDPOINT:
        raise ModelConfigError("AZURE_OPENAI_ENDPOINT must be set for the foundry provider")
    if MODEL_API_KEY != LOCAL_API_KEY:
        return OpenAIChatCompletionClient(model=MODEL_NAME, azure_endpoint=AZURE_OPENAI_ENDPOINT,
                                          api_key=MODEL_API_KEY, api_version=AZURE_OPENAI_API_VERSION)
    credential = DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID or None)
    return OpenAIChatCompletionClient(model=MODEL_NAME, azure_endpoint=AZURE_OPENAI_ENDPOINT,
                                      credential=credential, api_version=AZURE_OPENAI_API_VERSION)


def _gate(provider: ModelProvider) -> asyncio.Semaphore | None:
    """Concurrency gate: MODEL_MAX_CONCURRENCY when set (0 means unlimited), else 1 for local servers."""
    if MODEL_MAX_CONCURRENCY:
        limit = int(MODEL_MAX_CONCURRENCY)
        return asyncio.Semaphore(limit) if limit > 0 else None
    return asyncio.Semaphore(LOCAL_DEFAULT_CONCURRENCY) if provider in LOCAL_PROVIDERS else None
