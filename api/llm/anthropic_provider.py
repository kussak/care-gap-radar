"""Claude via the Anthropic API, using structured outputs for schema-valid JSON."""

import json
import logging
import os

import anthropic

from api.llm.provider import LLMError

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_TOKENS = 2000  # brief is ~500 output tokens; headroom for adaptive thinking


class AnthropicProvider:
    def __init__(self, model: str | None = None, client: anthropic.Anthropic | None = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self._client = client  # created lazily so constructing the provider never needs a key

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        return self._client

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Could not reach the Anthropic API: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e

        usage = response.usage
        log.info(
            "llm call model=%s input_tokens=%s output_tokens=%s stop_reason=%s request_id=%s",
            self.model, usage.input_tokens, usage.output_tokens, response.stop_reason,
            response._request_id,
        )
        if response.stop_reason == "refusal":
            raise LLMError("The model declined to write this brief.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The brief was cut off at max_tokens.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("The response contained no text block.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"The response was not valid JSON: {e}") from e
