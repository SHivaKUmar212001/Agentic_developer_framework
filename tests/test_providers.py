from __future__ import annotations

import pytest

from forge.core.providers import AnthropicProvider, OpenAIProvider, ProviderSetupError


def test_anthropic_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ProviderSetupError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()


def test_openai_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderSetupError, match="OPENAI_API_KEY"):
        OpenAIProvider()
