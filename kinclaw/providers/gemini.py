"""Google Gemini LLM provider."""
from __future__ import annotations

import json

from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider

# Available Gemini models
GEMINI_MODELS = {
    "gemini-2.5-flash": "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite-preview-06-17",
}


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Resolve alias or use raw model name
        self._model_name = GEMINI_MODELS.get(model, model)
        self._genai = genai
        logger.info("GeminiProvider initialized with model: {}", self._model_name)

    async def think(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        import asyncio
        from functools import partial

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        model = self._genai.GenerativeModel(
            self._model_name,
            generation_config={"max_output_tokens": max_tokens},
        )
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, partial(model.generate_content, full_prompt)
            )
            return response.text
        except Exception as e:
            logger.error("Gemini API error: {}", e)
            raise

    async def think_json(self, prompt: str, system: str = "") -> dict:
        text = await self.think(
            prompt=prompt + "\n\nRespond ONLY with valid JSON. No explanation.",
            system=system,
        )
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
