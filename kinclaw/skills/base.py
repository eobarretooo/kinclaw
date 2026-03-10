"""Abstract base class for all KinClaw skills."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the skill and return a result dict."""

    async def validate(self, **kwargs) -> bool:
        """Validate parameters before execution. Override for custom logic."""
        return True
