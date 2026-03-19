from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from forge.core.llm import call_llm, parse_json_response
from forge.core.state import SharedState, Task

if TYPE_CHECKING:
    from forge.core.config import AgentConfig


class BaseAgent(ABC):
    name: str = "base"
    system_prompt: str = ""

    def __init__(self, config: Optional["AgentConfig"] = None) -> None:
        self.config = config

    async def call(self, user_message: str, **kwargs: Any) -> str:
        model = kwargs.pop("model", None)
        max_tokens = kwargs.pop("max_tokens", None)
        temperature = kwargs.pop("temperature", None)

        if self.config is not None:
            model = model or self.config.model
            max_tokens = max_tokens or self.config.max_tokens
            if temperature is None:
                temperature = self.config.temperature

        return await call_llm(
            self.system_prompt,
            user_message,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def parse_json(self, text: str) -> dict[str, Any]:
        parsed = parse_json_response(text)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object from {self.name}, got {type(parsed).__name__}")
        return parsed

    @abstractmethod
    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the agent and return structured JSON."""
