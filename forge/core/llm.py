from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional

from anthropic import Anthropic

MODEL = os.getenv("FORGE_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.getenv("FORGE_MAX_TOKENS", "8192"))

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


async def call_llm(
    system: str,
    user_message: str,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    response = await asyncio.to_thread(
        get_client().messages.create,
        model=model or MODEL,
        max_tokens=max_tokens or MAX_TOKENS,
        temperature=0.3 if temperature is None else temperature,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    text_blocks = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return "\n".join(text_blocks).strip()


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
