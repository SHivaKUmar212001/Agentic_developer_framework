from __future__ import annotations

import json
import os
from typing import Any, Optional

from forge.core.providers import BaseProvider, get_provider as get_provider_client

MODEL = os.getenv("FORGE_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.getenv("FORGE_MAX_TOKENS", "8192"))


def get_provider(provider_name: Optional[str] = None) -> BaseProvider:
    return get_provider_client(provider_name or os.getenv("FORGE_PROVIDER", "anthropic"))


def clear_provider_cache() -> None:
    get_provider_client.cache_clear()  # type: ignore[attr-defined]


async def call_llm(
    system: str,
    user_message: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    agent_name: Optional[str] = None,
) -> str:
    return await get_provider(provider).complete(
        system=system,
        user_message=user_message,
        model=model or MODEL,
        max_tokens=max_tokens or MAX_TOKENS,
        temperature=0.3 if temperature is None else temperature,
        agent_name=agent_name,
    )


def parse_json_response(text: str) -> Any:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for opener, closer in (("{", "}"), ("[", "]")):
            start = cleaned.find(opener)
            end = cleaned.rfind(closer)
            if start != -1 and end != -1 and end > start:
                candidate = cleaned[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    raise ValueError(f"Could not parse JSON response: {text[:200]}")
