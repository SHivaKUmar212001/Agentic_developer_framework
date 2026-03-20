from __future__ import annotations

DEFAULT_PROVIDER = "anthropic"

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4.1-mini",
    "ollama": "llama3.1:8b",
    "mock": "mock-model",
}


def normalize_provider(name: str | None) -> str:
    return (name or DEFAULT_PROVIDER).strip().lower()


def default_model_for_provider(name: str | None) -> str:
    provider = normalize_provider(name)
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS[DEFAULT_PROVIDER])
