import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from kinclaw.core.state import AgentState, AgentPhase
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.bus import MessageBus
from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.types import Approval, Proposal, ProposalStatus
from kinclaw.database.connection import get_session, init_db
from kinclaw.database.queries import ApprovalRepo, ProposalRepo


def test_agent_state_initial():
    state = AgentState()
    assert state.phase == AgentPhase.IDLE
    assert state.proposals_today == 0
    assert state.is_running is False
    assert state.last_cycle_started_at is None


def test_agent_state_transitions():
    state = AgentState()
    state.phase = AgentPhase.ANALYZING
    assert state.phase == AgentPhase.ANALYZING


def test_agent_state_to_dict():
    state = AgentState()
    d = state.to_dict()
    assert d["phase"] == "idle"
    assert d["is_running"] is False
    assert d["last_analysis_metrics"] == {}
    assert d["last_cycle_started_at"] is None


@pytest.mark.asyncio
async def test_agent_run_cycle_records_last_cycle_started_at():
    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)

    agent = KinClawAgent(
        settings=settings, provider=mock_provider, bus=bus, router=router
    )

    await agent.run_improvement_cycle()

    assert agent.state.last_cycle_started_at is not None


@pytest.mark.asyncio
async def test_agent_analyze_self_returns_analysis():
    """analyze_self() returns metrics dict."""
    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)

    agent = KinClawAgent(
        settings=settings, provider=mock_provider, bus=bus, router=router
    )
    analysis = await agent.analyze_self()

    assert "metrics" in analysis
    assert analysis["metrics"]["files"] >= 0
    assert "gaps" in analysis


@pytest.mark.asyncio
async def test_agent_format_proposal_notification():
    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=mock_provider, bus=bus, router=router
    )

    proposal = Proposal(
        title="Test improvement",
        description="Adds caching",
        impact_pct=40,
        risk="low",
        confidence_pct=92,
        estimated_hours=2.0,
        reference_claw="nanobot",
    )
    msg = agent._format_proposal_notification(proposal)
    assert "Test improvement" in msg
    assert "aprova" in msg
    assert "40%" in msg


@pytest.mark.asyncio
async def test_agent_handles_inbound_approval_for_explicit_proposal_reference():
    """_handle_inbound() routes approval using explicit proposal correlation."""
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=mock_provider, bus=bus, router=router
    )

    proposal_one = Proposal(
        id="proposal-123",
        title="One",
        description="First proposal",
        confidence_pct=70,
    )
    proposal_two = Proposal(
        id="proposal-456",
        title="Two",
        description="Second proposal",
        confidence_pct=75,
    )

    await agent._save_proposal(proposal_one, status=ProposalStatus.SENT)
    await agent._save_proposal(proposal_two, status=ProposalStatus.SENT)
    agent._approval_queue.register_proposal("proposal-123")
    agent._approval_queue.register_proposal("proposal-456")
    agent._state.current_proposal_id = "proposal-123"

    from kinclaw.core.types import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="123",
        chat_id="123",
        content="aprova proposal-456",
    )
    await agent._handle_inbound(msg)

    approval = await agent._approval_queue.get_for("proposal-456", timeout=0.5)
    assert approval is not None
    assert approval.approved is True
    assert approval.proposal_id == "proposal-456"


@pytest.mark.asyncio
async def test_run_improvement_cycle_persists_selected_proposal_and_statuses():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-persisted",
        title="Persist me",
        description="Store proposal lifecycle in the database.",
        impact_pct=25,
        risk="low",
        confidence_pct=91,
        estimated_hours=1.5,
        reference_claw="ref-claw",
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 7, "lines": 101}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()
    agent._approval_queue.get_for = AsyncMock(
        return_value=Approval(
            proposal_id=proposal.id,
            approved=True,
            channel="telegram",
            raw_message="aprova",
        )
    )
    agent._executor.execute = AsyncMock(return_value={"success": True})

    await agent.run_improvement_cycle()

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.title == proposal.title
    assert record.status == "done"
    assert agent.state.last_analysis_metrics == {"files": 7, "lines": 101}


@pytest.mark.asyncio
async def test_run_improvement_cycle_marks_rejected_proposal_in_database():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-rejected",
        title="Reject me",
        description="Rejected proposal",
        confidence_pct=75,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 2, "lines": 9}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()
    agent._approval_queue.get_for = AsyncMock(
        return_value=Approval(
            proposal_id=proposal.id,
            approved=False,
            channel="telegram",
            raw_message="nega",
        )
    )
    agent._executor.execute = AsyncMock(
        return_value={"success": False, "reason": "rejected"}
    )

    await agent.run_improvement_cycle()

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.status == "rejected"


@pytest.mark.asyncio
async def test_run_improvement_cycle_leaves_unanswered_proposal_pending_for_later_cycle():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-timeout",
        title="Timeout me",
        description="No one responds to this proposal.",
        confidence_pct=80,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 3, "lines": 14}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()
    agent._approval_queue.get_for = AsyncMock(return_value=None)

    await agent.run_improvement_cycle()

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.status == ProposalStatus.SENT.value


@pytest.mark.asyncio
async def test_run_improvement_cycle_marks_pr_failure_with_distinct_status():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-pr-failed",
        title="PR creation fails",
        description="Commit/push works but PR creation does not.",
        confidence_pct=85,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 3, "lines": 14}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()
    agent._approval_queue.get_for = AsyncMock(
        return_value=Approval(
            proposal_id=proposal.id,
            approved=True,
            channel="telegram",
            raw_message="aprova",
        )
    )
    agent._executor.execute = AsyncMock(
        return_value={"success": False, "reason": "pr_failed", "stderr": "github down"}
    )

    await agent.run_improvement_cycle()

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.status == ProposalStatus.PR_FAILED.value


@pytest.mark.asyncio
async def test_run_improvement_cycle_cleans_up_after_execution_exception():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-exception",
        title="Explode during execution",
        description="Executor raises after approval.",
        confidence_pct=85,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 4, "lines": 20}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()
    agent._approval_queue.get_for = AsyncMock(
        return_value=Approval(
            proposal_id=proposal.id,
            approved=True,
            channel="telegram",
            raw_message="aprova",
        )
    )
    agent._executor.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await agent.run_improvement_cycle()

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.status == ProposalStatus.FAILED.value
    assert agent.state.current_proposal_id is None
    assert agent.state.phase == AgentPhase.IDLE
    assert agent.state.error == "boom"


@pytest.mark.asyncio
async def test_run_improvement_cycle_emits_actionable_proposal_without_waiting_for_approval():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal = Proposal(
        id="proposal-awaiting",
        title="Await approval asynchronously",
        description="Do not block the whole cycle while waiting.",
        confidence_pct=88,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 1, "lines": 1}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(return_value=[proposal])
    agent.broadcast = AsyncMock()

    await asyncio.wait_for(agent.run_improvement_cycle(), timeout=0.05)

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get(proposal.id)

    assert record is not None
    assert record.status == ProposalStatus.SENT.value
    assert agent.state.current_proposal_id is None
    assert agent.state.phase == AgentPhase.IDLE


@pytest.mark.asyncio
async def test_run_improvement_cycle_supports_multiple_pending_proposals_and_cleans_up_decisions():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )

    proposal_one = Proposal(
        id="proposal-one",
        title="First pending proposal",
        description="Waits for explicit approval.",
        confidence_pct=80,
    )
    proposal_two = Proposal(
        id="proposal-two",
        title="Second pending proposal",
        description="Can coexist with another pending proposal.",
        confidence_pct=81,
    )

    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 2, "lines": 3}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[{"type": "gap"}])
    agent._proposer.generate = AsyncMock(
        side_effect=[[proposal_one], [proposal_two], []]
    )
    agent.broadcast = AsyncMock()

    async def execute_side_effect(proposal, approval, notify_fn=None):
        if approval.approved:
            return {"success": True}
        return {"success": False, "reason": "rejected"}

    agent._executor.execute = AsyncMock(side_effect=execute_side_effect)

    await agent.run_improvement_cycle()
    await agent.run_improvement_cycle()

    from kinclaw.core.types import InboundMessage

    await agent._handle_inbound(
        InboundMessage(
            channel="telegram",
            sender_id="123",
            chat_id="123",
            content="nega proposal-one",
        )
    )
    await agent._handle_inbound(
        InboundMessage(
            channel="telegram",
            sender_id="123",
            chat_id="123",
            content="aprova proposal-two",
        )
    )

    await agent.run_improvement_cycle()

    async with get_session() as session:
        proposal_repo = ProposalRepo(session)
        approval_repo = ApprovalRepo(session)
        first_record = await proposal_repo.get("proposal-one")
        second_record = await proposal_repo.get("proposal-two")
        first_approval = await approval_repo.get_by_proposal_id("proposal-one")
        second_approval = await approval_repo.get_by_proposal_id("proposal-two")

    assert first_record is not None
    assert first_record.status == ProposalStatus.REJECTED.value
    assert second_record is not None
    assert second_record.status == ProposalStatus.DONE.value
    assert agent._executor.execute.await_count == 2
    assert first_approval is None
    assert second_approval is None
    assert agent._approval_queue.pending_count() == 0


@pytest.mark.asyncio
async def test_run_improvement_cycle_times_out_stale_pending_proposal_and_cleans_up():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )
    agent.broadcast = AsyncMock()
    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 2, "lines": 3}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[])

    stale_proposal = Proposal(
        id="proposal-stale",
        title="Stale pending proposal",
        description="Should time out in a later cycle.",
        confidence_pct=65,
    )
    await agent._save_proposal(stale_proposal, status=ProposalStatus.SENT)

    async with get_session() as session:
        repo = ProposalRepo(session)
        record = await repo.get("proposal-stale")
        assert record is not None
        record.created_at = datetime.utcnow() - timedelta(hours=2)
        await session.commit()

    await agent.run_improvement_cycle()

    async with get_session() as session:
        proposal_repo = ProposalRepo(session)
        approval_repo = ApprovalRepo(session)
        record = await proposal_repo.get("proposal-stale")
        approval = await approval_repo.get_by_proposal_id("proposal-stale")

    assert record is not None
    assert record.status == ProposalStatus.TIMED_OUT.value
    assert approval is None
    assert agent._approval_queue.pending_count() == 0


@pytest.mark.asyncio
async def test_run_improvement_cycle_marks_rehydrated_proposal_failed_on_processing_error():
    await init_db("sqlite+aiosqlite:///:memory:")

    settings = Settings(
        anthropic_api_key="test",
        github_token="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=AsyncMock(), bus=bus, router=router
    )
    agent.broadcast = AsyncMock()
    agent._analyzer.analyze = AsyncMock(
        return_value={"metrics": {"files": 1, "lines": 1}}
    )
    agent._comparator.find_gaps = AsyncMock(return_value=[])

    proposal = Proposal(
        id="proposal-rehydrated-failure",
        title="Pending proposal fails while processing",
        description="Previously persisted proposal with a stored approval.",
        confidence_pct=77,
    )
    await agent._save_proposal(proposal, status=ProposalStatus.SENT)
    await agent._approval_queue.submit(
        Approval(
            proposal_id=proposal.id,
            approved=True,
            channel="telegram",
            raw_message=f"aprova {proposal.id}",
        )
    )
    agent._executor.execute = AsyncMock(side_effect=RuntimeError("rehydrated boom"))

    with pytest.raises(RuntimeError, match="rehydrated boom"):
        await agent.run_improvement_cycle()

    async with get_session() as session:
        proposal_repo = ProposalRepo(session)
        approval_repo = ApprovalRepo(session)
        record = await proposal_repo.get(proposal.id)
        approval = await approval_repo.get_by_proposal_id(proposal.id)

    assert record is not None
    assert record.status == ProposalStatus.FAILED.value
    assert approval is None
    assert agent.state.error == "rehydrated boom"
