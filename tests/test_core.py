import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.core.state import AgentState, AgentPhase
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.bus import MessageBus
from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.types import Approval, Proposal, ProposalStatus
from kinclaw.database.connection import get_session, init_db
from kinclaw.database.queries import ProposalRepo


def test_agent_state_initial():
    state = AgentState()
    assert state.phase == AgentPhase.IDLE
    assert state.proposals_today == 0
    assert state.is_running is False


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
async def test_agent_handles_inbound_approval():
    """_handle_inbound() routes approval message to queue."""
    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)
    agent = KinClawAgent(
        settings=settings, provider=mock_provider, bus=bus, router=router
    )

    # Set a current proposal being awaited
    agent._state.current_proposal_id = "proposal-123"
    agent._approval_queue.register_proposal("proposal-123")

    from kinclaw.core.types import InboundMessage

    msg = InboundMessage(
        channel="telegram", sender_id="123", chat_id="123", content="aprova"
    )
    await agent._handle_inbound(msg)

    # Check it was submitted to queue
    approval = await agent._approval_queue.get_for("proposal-123", timeout=0.5)
    assert approval is not None
    assert approval.approved is True


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
async def test_run_improvement_cycle_marks_timed_out_proposal_as_sent():
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
    assert record.status == "sent"


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
