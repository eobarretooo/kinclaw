"""GitHub API skill via PyGithub."""
from __future__ import annotations

import asyncio
from functools import partial

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class GitHubAPISkill(BaseSkill):
    name = "github_api"
    description = "Create PRs, issues, and interact with GitHub."

    def __init__(self, token: str = "", repo: str = "") -> None:
        self._token = token
        self._repo = repo

    async def execute(
        self,
        action: str = "create_pr",
        title: str = "",
        body: str = "",
        head: str = "",
        base: str = "main",
        number: int = 0,
    ) -> dict:
        if not self._token:
            return {"error": "GitHub token not configured"}
        try:
            from github import Github
            g = Github(self._token)
            loop = asyncio.get_event_loop()
            repo = await loop.run_in_executor(None, g.get_repo, self._repo)

            if action == "create_pr":
                pr = await loop.run_in_executor(
                    None, partial(repo.create_pull, title=title, body=body, head=head, base=base)
                )
                return {"pr_number": pr.number, "url": pr.html_url, "success": True}
            elif action == "get_pr":
                pr = await loop.run_in_executor(None, repo.get_pull, number)
                return {"number": pr.number, "state": pr.state, "merged": pr.merged}
            elif action == "list_prs":
                prs = await loop.run_in_executor(
                    None, partial(repo.get_pulls, state="open")
                )
                return {"prs": [{"number": p.number, "title": p.title} for p in prs]}
        except Exception as e:
            logger.error("GitHub API error: {}", e)
            return {"error": str(e), "success": False}
        return {"error": f"Unknown action: {action}"}
