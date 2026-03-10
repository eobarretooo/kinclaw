import pytest
from unittest.mock import AsyncMock
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.core.types import Proposal, Approval


def test_parser_detects_approve():
    parser = ApprovalParser()
    result = parser.parse("aprova", proposal_id="p1")
    assert result is not None
    assert result.approved is True


def test_parser_detects_reject():
    parser = ApprovalParser()
    result = parser.parse("nega", proposal_id="p1")
    assert result is not None
    assert result.approved is False


def test_parser_detects_english_approve():
    parser = ApprovalParser()
    result = parser.parse("approve this", proposal_id="p1")
    assert result is not None
    assert result.approved is True


def test_parser_returns_none_for_unrelated():
    parser = ApprovalParser()
    result = parser.parse("como vai você?", proposal_id="p1")
    assert result is None


@pytest.mark.asyncio
async def test_queue_receive_approval():
    queue = ApprovalQueue()
    approval = Approval(proposal_id="p1", approved=True, channel="telegram", raw_message="aprova")
    await queue.submit(approval)
    received = await queue.get_for("p1", timeout=0.5)
    assert received is not None
    assert received.approved is True


@pytest.mark.asyncio
async def test_queue_timeout_returns_none():
    queue = ApprovalQueue()
    result = await queue.get_for("nonexistent_proposal", timeout=0.05)
    assert result is None


@pytest.mark.asyncio
async def test_executor_rejects_when_not_approved():
    safety = SafetyChecker()
    limiter = RateLimiter()
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(safety=safety, limiter=limiter, audit=audit)
    proposal = Proposal(title="X", description="Y", impact_pct=0, risk="low", confidence_pct=0, estimated_hours=1, code_changes={})
    approval = Approval(proposal_id=proposal.id, approved=False, channel="test", raw_message="nega")

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "rejected"


@pytest.mark.asyncio
async def test_executor_blocks_forbidden_path():
    safety = SafetyChecker()
    limiter = RateLimiter()
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(safety=safety, limiter=limiter, audit=audit)
    proposal = Proposal(
        title="Bad", description="Modifies guardrails", impact_pct=0, risk="high",
        confidence_pct=0, estimated_hours=0,
        code_changes={"kinclaw/guardrails/safety.py": "# hacked"},
    )
    approval = Approval(proposal_id=proposal.id, approved=True, channel="test", raw_message="aprova")

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "safety_violation"


@pytest.mark.asyncio
async def test_executor_blocks_when_commit_limit_reached():
    safety = SafetyChecker()
    limiter = RateLimiter(max_commits_per_day=0)
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(safety=safety, limiter=limiter, audit=audit)
    proposal = Proposal(title="Ok", description="Fine", impact_pct=5, risk="low", confidence_pct=80, estimated_hours=1, code_changes={})
    approval = Approval(proposal_id=proposal.id, approved=True, channel="test", raw_message="aprova")

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "commit_limit"
