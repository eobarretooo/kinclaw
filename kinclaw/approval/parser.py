"""Parses natural language approval/rejection from any channel."""

from __future__ import annotations

import re
from collections.abc import Iterable

from kinclaw.core.types import Approval

APPROVE_KEYWORDS = {
    "aprova",
    "approve",
    "yes",
    "sim",
    "ok",
    "go",
    "autoriza",
    "autorizo",
    "pode",
}
REJECT_KEYWORDS = {
    "nega",
    "reject",
    "no",
    "não",
    "nao",
    "cancel",
    "cancela",
    "stop",
    "abort",
}


class ApprovalParser:
    def parse(
        self,
        message: str,
        proposal_id: str | None = None,
        pending_proposal_ids: Iterable[str] | None = None,
        channel: str = "unknown",
    ) -> Approval | None:
        """Returns Approval if message is a clear approval/rejection, else None."""
        normalized = message.lower().strip()
        words = set(normalized.split())
        resolved_proposal_id = self._resolve_proposal_id(
            message=message,
            proposal_id=proposal_id,
            pending_proposal_ids=pending_proposal_ids,
        )

        if resolved_proposal_id is None:
            return None
        if words & APPROVE_KEYWORDS:
            return Approval(
                proposal_id=resolved_proposal_id,
                approved=True,
                channel=channel,
                raw_message=message,
            )
        if words & REJECT_KEYWORDS:
            return Approval(
                proposal_id=resolved_proposal_id,
                approved=False,
                channel=channel,
                raw_message=message,
            )
        return None

    def _resolve_proposal_id(
        self,
        message: str,
        proposal_id: str | None,
        pending_proposal_ids: Iterable[str] | None,
    ) -> str | None:
        if proposal_id is not None:
            return proposal_id

        candidate_ids = list(dict.fromkeys(pending_proposal_ids or []))
        if not candidate_ids:
            return None

        normalized = re.sub(r"[^a-z0-9_-]+", " ", message.lower())
        tokens = set(normalized.split())
        matches = [
            candidate for candidate in candidate_ids if candidate.lower() in tokens
        ]
        if len(matches) == 1:
            return matches[0]
        if len(candidate_ids) == 1:
            return candidate_ids[0]
        return None
