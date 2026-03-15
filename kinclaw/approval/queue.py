"""Manages pending proposals awaiting owner approval."""

from __future__ import annotations

import asyncio

from kinclaw.core.types import Approval
from kinclaw.database.connection import get_session
from kinclaw.database.queries import ApprovalRepo
from kinclaw.logger import logger


class ApprovalQueue:
    def __init__(self, persist_decisions: bool = False) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._approvals: dict[str, Approval] = {}
        self._persist_decisions = persist_decisions

    def register_proposal(self, proposal_id: str) -> None:
        self._events[proposal_id] = asyncio.Event()

    async def submit(self, approval: Approval) -> None:
        if self._persist_decisions:
            async with get_session() as session:
                repo = ApprovalRepo(session)
                await repo.save_decision(approval)
        self._approvals[approval.proposal_id] = approval
        if approval.proposal_id in self._events:
            self._events[approval.proposal_id].set()
        logger.info(
            "Approval submitted for proposal {}: {}",
            approval.proposal_id,
            approval.approved,
        )

    async def get_for(self, proposal_id: str, timeout: float = 3600) -> Approval | None:
        # Return immediately if approval already submitted before we started waiting
        if proposal_id in self._approvals:
            return self._approvals[proposal_id]
        if timeout <= 0:
            return await self.peek_for(proposal_id)
        if self._persist_decisions:
            persisted_approval = await self._load_persisted_approval(proposal_id)
            if persisted_approval is not None:
                self._approvals[proposal_id] = persisted_approval
                return persisted_approval
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

    async def peek_for(self, proposal_id: str) -> Approval | None:
        if proposal_id in self._approvals:
            return self._approvals[proposal_id]
        if not self._persist_decisions:
            return None
        persisted_approval = await self._load_persisted_approval(proposal_id)
        if persisted_approval is not None:
            self._approvals[proposal_id] = persisted_approval
        return persisted_approval

    async def forget(self, proposal_id: str) -> None:
        self.clear(proposal_id)
        if not self._persist_decisions:
            return
        async with get_session() as session:
            repo = ApprovalRepo(session)
            await repo.delete_for_proposal(proposal_id)

    def pending_count(self) -> int:
        return sum(1 for pid, ev in self._events.items() if not ev.is_set())

    def pending_ids(self) -> list[str]:
        return list(self._events)

    async def _load_persisted_approval(self, proposal_id: str) -> Approval | None:
        async with get_session() as session:
            repo = ApprovalRepo(session)
            record = await repo.get_by_proposal_id(proposal_id)

        if record is None:
            return None

        return Approval(
            proposal_id=record.proposal_id,
            approved=record.decision == "approved",
            channel=record.channel,
            raw_message=record.raw_message,
            decided_at=record.decided_at,
        )
