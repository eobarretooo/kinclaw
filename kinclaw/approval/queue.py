"""Manages pending proposals awaiting owner approval."""
from __future__ import annotations

import asyncio
from kinclaw.core.types import Approval
from kinclaw.logger import logger


class ApprovalQueue:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._approvals: dict[str, Approval] = {}

    def register_proposal(self, proposal_id: str) -> None:
        self._events[proposal_id] = asyncio.Event()

    async def submit(self, approval: Approval) -> None:
        self._approvals[approval.proposal_id] = approval
        if approval.proposal_id in self._events:
            self._events[approval.proposal_id].set()
        logger.info("Approval submitted for proposal {}: {}", approval.proposal_id, approval.approved)

    async def get_for(self, proposal_id: str, timeout: float = 3600) -> Approval | None:
        # Return immediately if approval already submitted before we started waiting
        if proposal_id in self._approvals:
            return self._approvals[proposal_id]
        if proposal_id not in self._events:
            self.register_proposal(proposal_id)
        try:
            await asyncio.wait_for(self._events[proposal_id].wait(), timeout=timeout)
            return self._approvals.get(proposal_id)
        except asyncio.TimeoutError:
            logger.warning("Approval timeout for proposal {}", proposal_id)
            return None

    def clear(self, proposal_id: str) -> None:
        self._events.pop(proposal_id, None)
        self._approvals.pop(proposal_id, None)

    def pending_count(self) -> int:
        return sum(1 for pid, ev in self._events.items() if not ev.is_set())
