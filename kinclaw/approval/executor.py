"""Executes approved proposals: write code, commit, push, open PR."""
from __future__ import annotations

from kinclaw.core.types import Approval, Proposal
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.logger import logger
from typing import Callable, Awaitable


NotifyFn = Callable[[str], Awaitable[None]] | None


class ApprovalExecutor:
    def __init__(
        self,
        safety: SafetyChecker,
        limiter: RateLimiter,
        audit: AuditLogger,
    ) -> None:
        self._safety = safety
        self._limiter = limiter
        self._audit = audit

    async def execute(self, proposal: Proposal, approval: Approval, notify_fn: NotifyFn = None) -> dict:
        """Execute an approved proposal end-to-end."""
        if not approval.approved:
            await self._audit.log("proposal_rejected", detail=proposal.title, result="rejected")
            if notify_fn:
                await notify_fn(f"❌ Proposal rejected: {proposal.title}")
            return {"success": False, "reason": "rejected"}

        violations = self._safety.validate_proposal_changes(proposal.code_changes)
        if violations:
            await self._audit.log("safety_violation", detail=str(violations), result="blocked")
            if notify_fn:
                await notify_fn(f"🚫 Safety check failed: {violations}")
            return {"success": False, "reason": "safety_violation", "violations": violations}

        if not await self._limiter.can_commit():
            if notify_fn:
                await notify_fn("⚠️ Daily commit limit reached. Execution deferred.")
            return {"success": False, "reason": "commit_limit"}

        if notify_fn:
            await notify_fn(f"✅ Approved! Starting execution of: {proposal.title}")

        await self._audit.log("proposal_executing", detail=proposal.title)
        return await self._do_execute(proposal, notify_fn)

    async def _do_execute(self, proposal: Proposal, notify_fn: NotifyFn) -> dict:
        """Write files, commit, push, open PR."""
        from kinclaw.skills.builtin.file_manager import FileManagerSkill
        from kinclaw.skills.builtin.git_manager import GitManagerSkill
        from kinclaw.skills.builtin.github_api import GitHubAPISkill
        from kinclaw.config import get_settings

        settings = get_settings()
        file_skill = FileManagerSkill()
        git_skill = GitManagerSkill()
        github_skill = GitHubAPISkill(token=settings.github_token, repo=settings.github_repo)

        # 1. Write code files
        if notify_fn:
            await notify_fn("💻 Writing code...")
        for path, content in proposal.code_changes.items():
            await file_skill.execute(action="write", path=path, content=content)

        # 2. Git add + commit
        if notify_fn:
            await notify_fn("📝 Committing changes...")
        files = list(proposal.code_changes.keys())
        await git_skill.execute(action="add", files=files)
        commit_result = await git_skill.execute(
            action="commit",
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

        # 3. Push
        if notify_fn:
            await notify_fn("📤 Pushing...")
        push_result = await git_skill.execute(action="push")
        if not push_result.get("success"):
            if notify_fn:
                await notify_fn(f"❌ Push failed: {push_result.get('stderr')}")
            return {"success": False, "reason": "push_failed"}

        # 4. Open PR
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
            head="auto-improve",
            base=settings.github_default_branch,
        )

        if pr_result.get("success"):
            if notify_fn:
                await notify_fn(f"✅ PR #{pr_result['pr_number']} opened!\n{pr_result['url']}")
            await self._audit.log("pr_opened", detail=pr_result.get("url", ""))
            return {"success": True, "pr_number": pr_result["pr_number"], "pr_url": pr_result["url"]}
        else:
            if notify_fn:
                await notify_fn(f"⚠️ Committed but PR creation failed: {pr_result.get('error')}")
            return {"success": True, "pr_number": None, "note": "pr_failed"}
