"""Discovers and loads all built-in skills into a registry."""
from __future__ import annotations

from kinclaw.skills.registry import SkillRegistry
from kinclaw.skills.builtin.file_manager import FileManagerSkill
from kinclaw.skills.builtin.code_executor import CodeExecutorSkill
from kinclaw.skills.builtin.git_manager import GitManagerSkill
from kinclaw.skills.builtin.github_api import GitHubAPISkill
from kinclaw.skills.builtin.web_search import WebSearchSkill
from kinclaw.skills.builtin.code_analyzer import CodeAnalyzerSkill


def load_builtin_skills(registry: SkillRegistry) -> None:
    """Register all built-in skills into the registry."""
    for SkillCls in [
        FileManagerSkill,
        CodeAnalyzerSkill,
        CodeExecutorSkill,
        GitManagerSkill,
        GitHubAPISkill,
        WebSearchSkill,
    ]:
        registry.register(SkillCls())
