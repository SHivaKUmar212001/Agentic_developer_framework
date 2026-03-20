from __future__ import annotations

import asyncio
import json
import os
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import httpx
from anthropic import Anthropic

from forge.core.provider_defaults import default_model_for_provider


class ProviderSetupError(RuntimeError):
    """Raised when a provider is selected but not configured correctly."""


class BaseProvider(ABC):
    name = "base"

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        agent_name: Optional[str] = None,
    ) -> str:
        """Return a text completion for the supplied prompt."""


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self) -> None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ProviderSetupError(
                "Anthropic is selected, but ANTHROPIC_API_KEY is not set.\n"
                "Set it once in your shell profile or before running forge:\n"
                '  export FORGE_PROVIDER="anthropic"\n'
                '  export ANTHROPIC_API_KEY="sk-ant-..."\n'
                "If you want a local model instead, switch to FORGE_PROVIDER=ollama."
            )
        self.client = Anthropic()

    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        agent_name: Optional[str] = None,
    ) -> str:
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(text_blocks).strip()


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI support requires the 'openai' package.") from exc

        if not os.getenv("OPENAI_API_KEY"):
            raise ProviderSetupError(
                "OpenAI is selected, but OPENAI_API_KEY is not set.\n"
                "Set it once in your shell profile or before running forge:\n"
                '  export FORGE_PROVIDER="openai"\n'
                '  export OPENAI_API_KEY="sk-..."\n'
                "If you want a local model instead, switch to FORGE_PROVIDER=ollama."
            )

        base_url = os.getenv("OPENAI_BASE_URL") or None
        self.client = OpenAI(base_url=base_url)

    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        agent_name: Optional[str] = None,
    ) -> str:
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message.content
        return message or ""


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        agent_name: Optional[str] = None,
    ) -> str:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        def _send() -> str:
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("message", {}).get("content", "")
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip()
                if "not found" in detail.lower():
                    raise ProviderSetupError(
                        f"Ollama is running, but model '{model}' is not available.\n"
                        f"Pull it first with:\n  ollama pull {model}\n"
                        f"Then run forge again. If you want the default local model, use:\n"
                        f'  export FORGE_PROVIDER="ollama"\n'
                        f'  export FORGE_MODEL="{default_model_for_provider("ollama")}"'
                    ) from exc
                raise ProviderSetupError(
                    f"Ollama returned an HTTP error while using model '{model}'.\n"
                    f"Host: {self.base_url}\n"
                    f"Details: {detail or exc}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderSetupError(
                    "Could not connect to Ollama.\n"
                    f"Expected host: {self.base_url}\n"
                    "Start Ollama and pull a local model first:\n"
                    "  ollama serve\n"
                    f"  ollama pull {default_model_for_provider('ollama')}\n"
                    '  export FORGE_PROVIDER="ollama"\n'
                    f'  export FORGE_MODEL="{default_model_for_provider("ollama")}"'
                ) from exc

        return await asyncio.to_thread(_send)


class MockProvider(BaseProvider):
    name = "mock"

    def __init__(self) -> None:
        responses_path = os.getenv("FORGE_MOCK_RESPONSES", "")
        if not responses_path:
            raise RuntimeError("FORGE_MOCK_RESPONSES must be set for the mock provider.")

        data = json.loads(Path(responses_path).read_text(encoding="utf-8"))
        self.responses = data.get("responses", data)
        if not isinstance(self.responses, list):
            raise ValueError("Mock provider responses must be a JSON list or an object with 'responses'.")
        self._lock = threading.Lock()
        self._used_indexes: set[int] = set()

    async def complete(
        self,
        *,
        system: str,
        user_message: str,
        model: str,
        max_tokens: int,
        temperature: float,
        agent_name: Optional[str] = None,
    ) -> str:
        with self._lock:
            selected_index: Optional[int] = None
            for index, current in enumerate(self.responses):
                if index in self._used_indexes:
                    continue

                if isinstance(current, dict):
                    expected_agent = current.get("agent")
                    contains = current.get("contains")
                    if expected_agent and expected_agent != agent_name:
                        continue
                    if contains and contains not in user_message:
                        continue
                selected_index = index
                break

            if selected_index is None:
                raise RuntimeError("Mock provider ran out of scripted responses.")

            self._used_indexes.add(selected_index)
            current = self.responses[selected_index]

        if isinstance(current, dict):
            expected_agent = current.get("agent")
            if expected_agent and expected_agent != agent_name:
                raise RuntimeError(
                    f"Mock response expected agent '{expected_agent}' but got '{agent_name}'."
                )
            return str(current.get("response", ""))

        return str(current)


@lru_cache(maxsize=None)
def get_provider(name: str) -> BaseProvider:
    normalized = name.lower().strip()
    if normalized == "anthropic":
        return AnthropicProvider()
    if normalized == "openai":
        return OpenAIProvider()
    if normalized == "ollama":
        return OllamaProvider()
    if normalized == "mock":
        return MockProvider()
    raise ValueError(f"Unsupported provider: {name}")
