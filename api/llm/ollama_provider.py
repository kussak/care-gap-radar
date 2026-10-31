"""Self-hosted model via Ollama: the swap path for real PHI, where data must not leave the network.

Not exercised live in this demo. Ollama's /api/chat accepts a JSON schema in `format` and returns
the JSON as the message content, so the brief logic works unchanged.
"""

import json
import logging
import os

import httpx

from api.llm.provider import LLMError

log = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": schema,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=120,
            )
            response.raise_for_status()
            body = response.json()
            log.info(
                "llm call model=%s input_tokens=%s output_tokens=%s",
                self.model, body.get("prompt_eval_count"), body.get("eval_count"),
            )
            return json.loads(body["message"]["content"])
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            raise LLMError(f"Ollama call failed: {e}") from e
