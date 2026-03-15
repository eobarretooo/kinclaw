"""Executes approved proposals in an isolated worktree."""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Protocol

from kinclaw.config import Settings, get_settings
from kinclaw.core.types import Approval, Proposal
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.skills.builtin.file_manager import FileManagerSkill
from kinclaw.skills.builtin.git_manager import GitManagerSkill
from kinclaw.skills.builtin.github_api import GitHubAPISkill


NotifyFn = Callable[[str], Awaitable[None]] | None


class Validator(Protocol):
    async def validate(self, workspace_path: str, proposal: Proposal) -> dict: ...


class ApprovalExecutor:
    def __init__(
        self,
        safety: SafetyChecker,
        limiter: RateLimiter,
        audit: AuditLogger,
        file_skill_factory: Callable[[], FileManagerSkill] | None = None,
        git_skill_factory: Callable[[], GitManagerSkill] | None = None,
        github_skill_factory: Callable[[], GitHubAPISkill] | None = None,
        validator_factory: Callable[[], Validator] | None = None,
        settings_factory: Callable[[], Settings] | None = None,
    ) -> None:
        self._safety = safety
        self._limiter = limiter
        self._audit = audit
        self._file_skill_factory = file_skill_factory or FileManagerSkill
        self._git_skill_factory = git_skill_factory or GitManagerSkill
        self._github_skill_factory = github_skill_factory
        self._validator_factory = validator_factory
        self._settings_factory = settings_factory or get_settings

    async def execute(
        self, proposal: Proposal, approval: Approval, notify_fn: NotifyFn = None
    ) -> dict:
        """Execute an approved proposal end-to-end."""
        if not approval.approved:
            await self._audit.log(
                "proposal_rejected", detail=proposal.title, result="rejected"
            )
            if notify_fn:
                await notify_fn(f"❌ Proposal rejected: {proposal.title}")
            return {"success": False, "reason": "rejected"}

        proposed_changes = {**proposal.code_changes, **proposal.test_changes}
        violations = self._safety.validate_proposal_changes(proposed_changes)
        if violations:
            await self._audit.log(
                "safety_violation", detail=str(violations), result="blocked"
            )
            if notify_fn:
                await notify_fn(f"🚫 Safety check failed: {violations}")
            return {
                "success": False,
                "reason": "safety_violation",
                "violations": violations,
            }

        if not await self._limiter.can_commit():
            if notify_fn:
                await notify_fn("⚠️ Daily commit limit reached. Execution deferred.")
            return {"success": False, "reason": "commit_limit"}

        if notify_fn:
            await notify_fn(f"✅ Approved! Starting execution of: {proposal.title}")

        await self._audit.log("proposal_executing", detail=proposal.title)
        return await self._do_execute(proposal, notify_fn)

    async def _do_execute(self, proposal: Proposal, notify_fn: NotifyFn) -> dict:
        """Write files in an isolated workspace, validate, then commit/push/open PR."""
        from kinclaw.approval.validator import ProposalValidator

        settings = self._settings_factory()
        file_skill = self._file_skill_factory()
        git_skill = self._git_skill_factory()
        github_factory = self._github_skill_factory or (
            lambda: GitHubAPISkill(
                token=settings.github_token, repo=settings.github_repo
            )
        )
        github_skill = github_factory()
        validator_factory = self._validator_factory or ProposalValidator
        validator = validator_factory()

        workspace_result = await git_skill.execute(
            action="prepare_workspace",
            proposal_id=proposal.id,
            title=proposal.title,
        )
        if not workspace_result.get("success"):
            return {
                "success": False,
                "reason": "workspace_failed",
                "stderr": workspace_result.get("stderr", ""),
            }

        workspace_path = Path(workspace_result["cwd"])
        branch_name = workspace_result["branch"]
        all_changes = {**proposal.code_changes, **proposal.test_changes}

        delete_branch = True
        try:
            if notify_fn:
                await notify_fn("💻 Writing code in isolated workspace...")
            for relative_path, content in all_changes.items():
                await file_skill.execute(
                    action="write",
                    path=str(workspace_path / relative_path),
                    content=content,
                )

            if notify_fn:
                await notify_fn("🧪 Validating changes...")
            validation_result = await validator.validate(str(workspace_path), proposal)
            if not validation_result.get("success"):
                if notify_fn:
                    await notify_fn(
                        f"❌ Validation failed: {validation_result.get('stderr', '')}"
                    )
                return {
                    "success": False,
                    "reason": "validation_failed",
                    "stderr": validation_result.get("stderr", ""),
                }

            if notify_fn:
                await notify_fn("📝 Committing changes...")
            files = list(all_changes.keys())
            await git_skill.execute(action="add", files=files, cwd=str(workspace_path))
            commit_result = await git_skill.execute(
                action="commit",
                cwd=str(workspace_path),
                message=(
                    f"Auto: {proposal.title}\n\n"
                    f"Impact: {proposal.impact_pct}% | Risk: {proposal.risk} | "
                    f"Confidence: {proposal.confidence_pct}%"
                ),
            )
            if not commit_result.get("success"):
                if notify_fn:
                    await notify_fn(f"❌ Commit failed: {commit_result.get('stderr')}")
                return {"success": False, "reason": "commit_failed"}

            await self._limiter.record_commit()

            if notify_fn:
                await notify_fn("📤 Pushing...")
            push_result = await git_skill.execute(
                action="push", cwd=str(workspace_path), branch=branch_name
            )
            if not push_result.get("success"):
                if notify_fn:
                    await notify_fn(f"❌ Push failed: {push_result.get('stderr')}")
                return {"success": False, "reason": "push_failed"}

            delete_branch = False

            if notify_fn:
                await notify_fn("🔗 Opening PR...")
            pr_result = await github_skill.execute(
                action="create_pr",
                title=proposal.title,
                body=(
                    f"## Auto-improvement\n\n{proposal.description}\n\n"
                    f"**Impact:** {proposal.impact_pct}%\n"
                    f"**Risk:** {proposal.risk}\n"
                    f"**Confidence:** {proposal.confidence_pct}%"
                ),
                head=branch_name,
                base=settings.github_default_branch,
            )

            if pr_result.get("success"):
                if notify_fn:
                    await notify_fn(
                        f"✅ PR #{pr_result['pr_number']} opened!\n{pr_result['url']}"
                    )
                await self._audit.log("pr_opened", detail=pr_result.get("url", ""))
                return {
                    "success": True,
                    "pr_number": pr_result["pr_number"],
                    "pr_url": pr_result["url"],
                }

            if notify_fn:
                await notify_fn(
                    f"⚠️ Committed but PR creation failed: {pr_result.get('error')}"
                )
            return {"success": True, "pr_number": None, "note": "pr_failed"}
        finally:
            await git_skill.execute(
                action="cleanup_workspace",
                cwd=str(workspace_path),
                branch=branch_name,
                delete_branch=delete_branch,
            )
