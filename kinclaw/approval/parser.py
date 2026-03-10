"""Parses natural language approval/rejection from any channel."""
from __future__ import annotations

from kinclaw.core.types import Approval

APPROVE_KEYWORDS = {"aprova", "approve", "yes", "sim", "ok", "go", "autoriza", "autorizo", "pode"}
REJECT_KEYWORDS = {"nega", "reject", "no", "não", "nao", "cancel", "cancela", "stop", "abort"}


class ApprovalParser:
    def parse(self, message: str, proposal_id: str, channel: str = "unknown") -> Approval | None:
        """Returns Approval if message is a clear approval/rejection, else None."""
        normalized = message.lower().strip()
        words = set(normalized.split())

        if words & APPROVE_KEYWORDS:
            return Approval(proposal_id=proposal_id, approved=True, channel=channel, raw_message=message)
        if words & REJECT_KEYWORDS:
            return Approval(proposal_id=proposal_id, approved=False, channel=channel, raw_message=message)
        return None
