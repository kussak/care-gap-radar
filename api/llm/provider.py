"""LLM provider abstraction. Swap providers via LLM_PROVIDER without touching brief logic."""

import os
from typing import Protocol


class LLMError(Exception):
    """The provider failed or returned something unusable."""


class LLMProvider(Protocol):
    model: str

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        """Return a JSON object conforming to `schema`."""
        ...


def get_provider() -> LLMProvider:
    name = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if name == "anthropic":
        from api.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "ollama":
        from api.llm.ollama_provider import OllamaProvider

        return OllamaProvider()
    if name == "fake":
        from api.llm.fake_provider import FakeProvider

        return FakeProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r}")
