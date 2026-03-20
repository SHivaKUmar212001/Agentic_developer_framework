from __future__ import annotations

import asyncio

import httpx
import pytest

from forge.core.providers import (
    AnthropicProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderSetupError,
)


def test_anthropic_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ProviderSetupError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()


def test_openai_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderSetupError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_ollama_provider_surfaces_connection_help(monkeypatch) -> None:
    class BrokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("forge.core.providers.httpx.Client", BrokenClient)

    provider = OllamaProvider()

    with pytest.raises(ProviderSetupError, match="ollama serve"):
        asyncio.run(
            provider.complete(
                system="sys",
                user_message="hello",
                model="llama3.1:8b",
                max_tokens=32,
                temperature=0.0,
            )
        )
