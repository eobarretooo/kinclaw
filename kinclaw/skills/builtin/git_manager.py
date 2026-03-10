"""Git operations skill."""
from __future__ import annotations

import asyncio

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


async def _run_git(*args: str, cwd: str = ".") -> dict:
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
        "success": proc.returncode == 0,
    }


class GitManagerSkill(BaseSkill):
    name = "git_manager"
    description = "Run git operations: status, add, commit, push, branch."

    async def execute(
        self,
        action: str = "status",
        message: str = "",
        files: list[str] | None = None,
        branch: str = "",
        cwd: str = ".",
    ) -> dict:
        if action == "status":
            return await _run_git("status", "--short", cwd=cwd)
        elif action == "add":
            targets = files or ["."]
            return await _run_git("add", *targets, cwd=cwd)
        elif action == "commit":
            if not message:
                return {"error": "Commit message required"}
            return await _run_git("commit", "-m", message, cwd=cwd)
        elif action == "push":
            return await _run_git("push", cwd=cwd)
        elif action == "checkout_branch":
            if not branch:
                return {"error": "Branch name required"}
            return await _run_git("checkout", "-b", branch, cwd=cwd)
        elif action == "diff":
            return await _run_git("diff", "--stat", "HEAD", cwd=cwd)
        return {"error": f"Unknown action: {action}"}
