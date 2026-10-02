"""Tests for environment-driven adapters: model runtime selection and telemetry setup.

Module-level configuration constants are patched per test, mirroring how environment variables configure them.
No network calls are made; Foundry clients are constructed but never invoked.
"""

import pytest

from insidegame.adapters import model_client, telemetry
from insidegame.adapters.model_client import ModelProvider, build_model_runtime
from insidegame.core.exceptions import ModelConfigError


def test_offline_runtime_makes_no_model_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_client, "MODEL_PROVIDER", "offline")
    runtime = build_model_runtime()
    assert runtime.provider is ModelProvider.OFFLINE and runtime.policy.max_attempts == 0


def test_mlx_runtime_inlines_schema_and_serialises_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_client, "MODEL_PROVIDER", "mlx")
    monkeypatch.setattr(model_client, "MODEL_MAX_CONCURRENCY", "")
    policy = build_model_runtime().policy
    assert policy.inline_schema and policy.gate is not None


def test_foundry_requires_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_client, "MODEL_PROVIDER", "foundry")
    monkeypatch.setattr(model_client, "AZURE_OPENAI_ENDPOINT", "")
    with pytest.raises(ModelConfigError):
        build_model_runtime()


def test_foundry_uses_keyless_auth_and_native_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_client, "MODEL_PROVIDER", "foundry")
    monkeypatch.setattr(model_client, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setattr(model_client, "MODEL_API_KEY", model_client.LOCAL_API_KEY)
    monkeypatch.setattr(model_client, "MODEL_MAX_CONCURRENCY", "")
    runtime = build_model_runtime()
    assert runtime.provider is ModelProvider.FOUNDRY
    assert not runtime.policy.inline_schema and runtime.policy.gate is None and runtime.policy.prompt_suffix == ""


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_client, "MODEL_PROVIDER", "mystery")
    with pytest.raises(ModelConfigError):
        build_model_runtime()


def test_telemetry_is_off_without_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    assert telemetry.setup_telemetry() is False
