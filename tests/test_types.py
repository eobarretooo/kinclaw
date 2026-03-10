from kinclaw.core.types import (
    InboundMessage, OutboundMessage, Proposal, ProposalStatus, Approval,
)


def test_inbound_message_defaults():
    msg = InboundMessage(channel="telegram", sender_id="123", chat_id="123", content="hi")
    assert msg.id is not None
    assert msg.media == []


def test_proposal_status_lifecycle():
    p = Proposal(
        title="Test improvement",
        description="Add caching to memory.py",
        impact_pct=40,
        risk="low",
        confidence_pct=92,
        estimated_hours=2.0,
        code_changes={},
    )
    assert p.status == ProposalStatus.PENDING
    assert p.id is not None


def test_approval_approved():
    a = Approval(proposal_id="abc", approved=True, channel="telegram", raw_message="aprova")
    assert a.approved is True
