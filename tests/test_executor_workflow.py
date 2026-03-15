from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.approval.validator import ProposalValidator
from kinclaw.config import Settings
from kinclaw.core.types import Approval, Proposal
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.skills.builtin.git_manager import GitManagerSkill


class FakeFileManagerSkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"success": True, "path": kwargs.get("path")}


class FakeGitManagerSkill:
    def __init__(self, workspace_path: Path, branch_name: str) -> None:
        self.workspace_path = workspace_path
        self.branch_name = branch_name
        self.calls: list[dict] = []

    async def execute(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        action = kwargs["action"]
        if action == "prepare_workspace":
            return {
                "success": True,
                "cwd": str(self.workspace_path),
                "branch": self.branch_name,
            }
        if action in {"add", "commit", "push", "cleanup_workspace"}:
            return {"success": True}
        raise AssertionError(f"Unexpected git action: {action}")


class FakeGitHubAPISkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"success": True, "pr_number": 12, "url": "https://example.test/pr/12"}


class FakeValidator:
    def __init__(self, result: dict | None = None) -> None:
        self.calls: list[dict] = []
        self.result = result or {"success": True, "commands": [".venv/bin/pytest"]}

    async def validate(self, workspace_path: str, proposal: Proposal) -> dict:
        self.calls.append({"workspace_path": workspace_path, "proposal": proposal})
        return self.result


def _proposal(**overrides) -> Proposal:
    data = {
        "title": "Add isolated executor",
        "description": "Apply approved changes safely",
        "impact_pct": 12,
        "risk": "low",
        "confidence_pct": 89,
        "estimated_hours": 2,
        "code_changes": {"src/feature.py": "print('code')\n"},
        "test_changes": {"tests/test_feature.py": "def test_ok():\n    assert True\n"},
    }
    data.update(overrides)
    return Proposal(**data)


def _approval_for(proposal: Proposal) -> Approval:
    return Approval(
        proposal_id=proposal.id, approved=True, channel="test", raw_message="aprova"
    )


@pytest.mark.asyncio
async def test_executor_uses_isolated_workspace_and_real_branch_for_pr(tmp_path):
    workspace_path = tmp_path / "proposal-worktree"
    git_skill = FakeGitManagerSkill(
        workspace_path=workspace_path, branch_name="proposal/add-isolated-executor"
    )
    file_skill = FakeFileManagerSkill()
    github_skill = FakeGitHubAPISkill()
    validator = FakeValidator()

    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(
        safety=SafetyChecker(),
        limiter=RateLimiter(),
        audit=audit,
        file_skill_factory=lambda: file_skill,
        git_skill_factory=lambda: git_skill,
        github_skill_factory=lambda: github_skill,
        validator_factory=lambda: validator,
        settings_factory=lambda: Settings(
            github_token="token", github_repo="owner/repo"
        ),
    )

    proposal = _proposal()
    result = await executor.execute(proposal, _approval_for(proposal))

    assert result["success"] is True
    assert git_skill.calls[0]["action"] == "prepare_workspace"
    assert validator.calls == [
        {"workspace_path": str(workspace_path), "proposal": proposal}
    ]
    assert [
        call["cwd"]
        for call in git_skill.calls
        if call["action"] in {"add", "commit", "push"}
    ] == [
        str(workspace_path),
        str(workspace_path),
        str(workspace_path),
    ]
    assert [Path(call["path"]) for call in file_skill.calls] == [
        workspace_path / "src/feature.py",
        workspace_path / "tests/test_feature.py",
    ]
    assert github_skill.calls[0]["head"] == "proposal/add-isolated-executor"


@pytest.mark.asyncio
async def test_executor_blocks_commit_push_and_pr_when_validation_fails(tmp_path):
    workspace_path = tmp_path / "proposal-worktree"
    git_skill = FakeGitManagerSkill(
        workspace_path=workspace_path, branch_name="proposal/validation-failure"
    )
    file_skill = FakeFileManagerSkill()
    github_skill = FakeGitHubAPISkill()
    validator = FakeValidator(result={"success": False, "stderr": "tests failed"})

    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(
        safety=SafetyChecker(),
        limiter=RateLimiter(),
        audit=audit,
        file_skill_factory=lambda: file_skill,
        git_skill_factory=lambda: git_skill,
        github_skill_factory=lambda: github_skill,
        validator_factory=lambda: validator,
        settings_factory=lambda: Settings(
            github_token="token", github_repo="owner/repo"
        ),
    )

    proposal = _proposal(title="Validation failure")
    result = await executor.execute(proposal, _approval_for(proposal))

    assert result == {
        "success": False,
        "reason": "validation_failed",
        "stderr": "tests failed",
    }
    assert [call["action"] for call in git_skill.calls] == [
        "prepare_workspace",
        "cleanup_workspace",
    ]
    assert github_skill.calls == []
    assert [Path(call["path"]) for call in file_skill.calls] == [
        workspace_path / "src/feature.py",
        workspace_path / "tests/test_feature.py",
    ]


@pytest.mark.asyncio
async def test_executor_blocks_unsafe_test_changes_before_workspace_setup(tmp_path):
    git_skill = FakeGitManagerSkill(
        workspace_path=tmp_path / "proposal-worktree", branch_name="proposal/unsafe"
    )

    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(
        safety=SafetyChecker(),
        limiter=RateLimiter(),
        audit=audit,
        git_skill_factory=lambda: git_skill,
    )

    proposal = _proposal(
        test_changes={"tests/test_feature.py": "os.system('rm -rf /')\n"}
    )
    result = await executor.execute(proposal, _approval_for(proposal))

    assert result["success"] is False
    assert result["reason"] == "safety_violation"
    assert any("Dangerous content" in violation for violation in result["violations"])
    assert git_skill.calls == []


@pytest.mark.asyncio
async def test_validator_runs_pytest_and_ruff_when_available(tmp_path, monkeypatch):
    tool_root = tmp_path / "tool-root"
    (tool_root / ".venv/bin").mkdir(parents=True)
    (tool_root / ".venv/bin/pytest").write_text("", encoding="utf-8")
    (tool_root / ".venv/bin/ruff").write_text("", encoding="utf-8")

    commands: list[tuple[list[str], str]] = []

    async def fake_run(command: list[str], cwd: str) -> dict:
        commands.append((command, cwd))
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

    validator = ProposalValidator(tool_root=tool_root)
    monkeypatch.setattr(validator, "_run", fake_run)

    result = await validator.validate(str(tmp_path / "workspace"), _proposal())

    assert result["success"] is True
    assert commands == [
        ([str(tool_root / ".venv/bin/pytest")], str(tmp_path / "workspace")),
        (
            [str(tool_root / ".venv/bin/ruff"), "check", "."],
            str(tmp_path / "workspace"),
        ),
    ]


@pytest.mark.asyncio
async def test_git_cleanup_deletes_branch_from_repo_root(monkeypatch):
    calls: list[tuple[tuple[str, ...], str]] = []

    async def fake_run_git(*args: str, cwd: str = ".") -> dict:
        calls.append((args, cwd))
        if args == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return {
                "success": True,
                "stdout": "/repo/.git",
                "stderr": "",
                "returncode": 0,
            }
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr("kinclaw.skills.builtin.git_manager._run_git", fake_run_git)

    skill = GitManagerSkill()
    result = await skill.execute(
        action="cleanup_workspace",
        cwd="/repo/.worktrees/approved/proposal-x",
        branch="proposal/x",
        delete_branch=True,
    )

    assert result["success"] is True
    assert calls == [
        (
            ("rev-parse", "--path-format=absolute", "--git-common-dir"),
            "/repo/.worktrees/approved/proposal-x",
        ),
        (
            ("worktree", "remove", "--force", "/repo/.worktrees/approved/proposal-x"),
            "/repo/.worktrees/approved/proposal-x",
        ),
        (("branch", "-D", "proposal/x"), "/repo"),
    ]
