"""Central registry for all loaded skills."""
from __future__ import annotations

from kinclaw.logger import logger
from kinclaw.skills.base import BaseSkill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill
        logger.debug("Skill registered: {}", skill.name)

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills.keys())

    def all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    async def execute(self, name: str, **kwargs) -> dict:
        skill = self.get(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name}")
        if not await skill.validate(**kwargs):
            raise ValueError(f"Invalid parameters for skill: {name}")
        return await skill.execute(**kwargs)
