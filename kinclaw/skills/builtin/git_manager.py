"""Git operations skill."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from kinclaw.skills.base import BaseSkill


async def _run_git(*args: str, cwd: str = ".") -> dict:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "proposal"


class GitManagerSkill(BaseSkill):
    name = "git_manager"
    description = "Run git operations: status, add, commit, push, branch."

    async def execute(
        self,
        action: str = "status",
        message: str = "",
        files: list[str] | None = None,
        branch: str = "",
        title: str = "",
        proposal_id: str = "",
        cwd: str = ".",
        delete_branch: bool = False,
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
            if branch:
                return await _run_git("push", "-u", "origin", branch, cwd=cwd)
            return await _run_git("push", cwd=cwd)
        elif action == "checkout_branch":
            if not branch:
                return {"error": "Branch name required"}
            return await _run_git("checkout", "-b", branch, cwd=cwd)
        elif action == "diff":
            return await _run_git("diff", "--stat", "HEAD", cwd=cwd)
        elif action == "prepare_workspace":
            repo_root_result = await _run_git("rev-parse", "--show-toplevel", cwd=cwd)
            if not repo_root_result.get("success"):
                return repo_root_result

            repo_root = Path(repo_root_result["stdout"])
            branch_name = branch or f"proposal/{_slugify(title)}-{proposal_id[:8]}"
            workspace_root = repo_root / ".worktrees" / "approved"
            workspace_root.mkdir(parents=True, exist_ok=True)
            workspace_path = workspace_root / branch_name.replace("/", "-")
            result = await _run_git(
                "worktree",
                "add",
                "-b",
                branch_name,
                str(workspace_path),
                "HEAD",
                cwd=cwd,
            )
            if not result.get("success"):
                return result
            return result | {"cwd": str(workspace_path), "branch": branch_name}
        elif action == "cleanup_workspace":
            common_dir_result = await _run_git(
                "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd
            )
            if not common_dir_result.get("success"):
                return common_dir_result

            repo_root = str(Path(common_dir_result["stdout"]).parent)
            result = await _run_git("worktree", "remove", "--force", cwd, cwd=cwd)
            if delete_branch and branch:
                branch_result = await _run_git("branch", "-D", branch, cwd=repo_root)
                if not branch_result.get("success"):
                    return branch_result
            return result
        return {"error": f"Unknown action: {action}"}
