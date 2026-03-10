"""Abstract LLM provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def think(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        """Send prompt, return text response."""

    @abstractmethod
    async def think_json(self, prompt: str, system: str = "") -> dict:
        """Send prompt expecting JSON response, return parsed dict."""
