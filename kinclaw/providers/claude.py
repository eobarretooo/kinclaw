"""Claude (Anthropic) LLM provider."""
from __future__ import annotations

import json

import anthropic

from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def think(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API error: {}", e)
            raise

    async def think_json(self, prompt: str, system: str = "") -> dict:
        """Call think() and parse JSON from the response."""
        text = await self.think(
            prompt=prompt + "\n\nRespond ONLY with valid JSON. No explanation.",
            system=system,
        )
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
