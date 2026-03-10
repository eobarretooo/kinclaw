import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.core.state import AgentState, AgentPhase
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.bus import MessageBus
from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.types import Proposal


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


@pytest.mark.asyncio
async def test_agent_analyze_self_returns_analysis():
    """analyze_self() returns metrics dict."""
    settings = Settings(anthropic_api_key="test", github_token="test")
    mock_provider = AsyncMock()
    bus = MessageBus()
    router = ChannelRouter(bus)

    agent = KinClawAgent(settings=settings, provider=mock_provider, bus=bus, router=router)
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
    agent = KinClawAgent(settings=settings, provider=mock_provider, bus=bus, router=router)

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
    agent = KinClawAgent(settings=settings, provider=mock_provider, bus=bus, router=router)

    # Set a current proposal being awaited
    agent._state.current_proposal_id = "proposal-123"
    agent._approval_queue.register_proposal("proposal-123")

    from kinclaw.core.types import InboundMessage
    msg = InboundMessage(channel="telegram", sender_id="123", chat_id="123", content="aprova")
    await agent._handle_inbound(msg)

    # Check it was submitted to queue
    approval = await agent._approval_queue.get_for("proposal-123", timeout=0.5)
    assert approval is not None
    assert approval.approved is True
