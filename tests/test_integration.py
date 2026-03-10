"""Integration tests for the full approval-execution pipeline."""
import pytest
from unittest.mock import AsyncMock
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.core.types import Proposal, Approval


@pytest.mark.asyncio
async def test_full_approval_pipeline_approve():
    """End-to-end: parse message → submit → receive."""
    parser = ApprovalParser()
    queue = ApprovalQueue()

    proposal = Proposal(
        title="Test integration improvement",
        description="Just for testing",
        impact_pct=10,
        risk="low",
        confidence_pct=95,
        estimated_hours=0.5,
        code_changes={},
    )

    queue.register_proposal(proposal.id)
    approval = parser.parse("aprova", proposal_id=proposal.id, channel="telegram")
    assert approval is not None
    await queue.submit(approval)

    received = await queue.get_for(proposal.id, timeout=1.0)
    assert received is not None
    assert received.approved is True


@pytest.mark.asyncio
async def test_full_approval_pipeline_reject():
    """Parse rejection → submit → receive."""
    parser = ApprovalParser()
    queue = ApprovalQueue()

    proposal = Proposal(
        title="Test rejection",
        description="Will be rejected",
        impact_pct=5,
        risk="medium",
        confidence_pct=50,
        estimated_hours=1,
        code_changes={},
    )

    queue.register_proposal(proposal.id)
    approval = parser.parse("nega isso", proposal_id=proposal.id, channel="discord")
    assert approval is not None
    assert approval.approved is False
    await queue.submit(approval)

    received = await queue.get_for(proposal.id, timeout=1.0)
    assert received is not None
    assert received.approved is False


@pytest.mark.asyncio
async def test_safety_blocks_forbidden_path():
    """Executor refuses proposals that modify guardrails."""
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(
        safety=SafetyChecker(),
        limiter=RateLimiter(),
        audit=audit,
    )

    proposal = Proposal(
        title="Malicious proposal",
        description="Tries to modify guardrails",
        impact_pct=0,
        risk="high",
        confidence_pct=0,
        estimated_hours=0,
        code_changes={"kinclaw/guardrails/safety.py": "# hacked"},
    )
    approval = Approval(
        proposal_id=proposal.id, approved=True,
        channel="test", raw_message="aprova"
    )

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "safety_violation"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_execution():
    """Executor respects daily commit limit."""
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(
        safety=SafetyChecker(),
        limiter=RateLimiter(max_commits_per_day=0),
        audit=audit,
    )

    proposal = Proposal(
        title="Safe proposal",
        description="Valid but limit exceeded",
        impact_pct=5, risk="low", confidence_pct=80,
        estimated_hours=1, code_changes={},
    )
    approval = Approval(
        proposal_id=proposal.id, approved=True,
        channel="test", raw_message="aprova"
    )

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "commit_limit"


@pytest.mark.asyncio
async def test_analyzer_and_comparator_integration():
    """SelfAnalyzer output feeds correctly into ClawComparator."""
    from pathlib import Path
    from kinclaw.auto_improve.analyzer import SelfAnalyzer
    from kinclaw.auto_improve.comparator import ClawComparator

    analyzer = SelfAnalyzer(base_path=Path("."))
    comparator = ClawComparator(ref_path=Path("ref"))

    analysis = await analyzer.analyze()
    gaps = await comparator.find_gaps(analysis)

    # kinclaw package now has enough files to produce gaps
    assert isinstance(gaps, list)
    assert len(gaps) > 0
    for gap in gaps:
        assert "type" in gap
        assert "reference_claw" in gap
        assert "self_metrics" in gap
