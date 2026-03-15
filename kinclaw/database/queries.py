"""Data-access helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinclaw.core.types import Approval, Proposal, ProposalStatus
from kinclaw.database.models import ApprovalDecisionRecord, AuditRecord, ProposalRecord


class ProposalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, **kwargs) -> ProposalRecord:
        rec = ProposalRecord(**kwargs)
        self._s.add(rec)
        await self._s.commit()
        await self._s.refresh(rec)
        return rec

    async def get(self, proposal_id: str) -> ProposalRecord | None:
        result = await self._s.execute(
            select(ProposalRecord).where(ProposalRecord.id == proposal_id)
        )
        return result.scalar_one_or_none()

    async def save_proposal(
        self, proposal: Proposal, status: ProposalStatus | str | None = None
    ) -> ProposalRecord:
        rec = await self.get(proposal.id)
        status_value = status.value if isinstance(status, ProposalStatus) else status
        values = {
            "title": proposal.title,
            "description": proposal.description,
            "impact_pct": proposal.impact_pct,
            "risk": proposal.risk,
            "confidence_pct": proposal.confidence_pct,
            "estimated_hours": proposal.estimated_hours,
            "code_changes": proposal.code_changes,
            "test_changes": proposal.test_changes,
            "reference_claw": proposal.reference_claw,
            "status": status_value or proposal.status.value,
        }
        if rec is None:
            rec = ProposalRecord(id=proposal.id, **values)
            self._s.add(rec)
        else:
            for key, value in values.items():
                setattr(rec, key, value)
        await self._s.commit()
        await self._s.refresh(rec)
        return rec

    async def list_by_status(
        self, status: ProposalStatus | str
    ) -> list[ProposalRecord]:
        status_value = status.value if isinstance(status, ProposalStatus) else status
        result = await self._s.execute(
            select(ProposalRecord)
            .where(ProposalRecord.status == status_value)
            .order_by(ProposalRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_statuses(
        self, statuses: list[ProposalStatus | str]
    ) -> list[ProposalRecord]:
        status_values = [
            s.value if isinstance(s, ProposalStatus) else s for s in statuses
        ]
        result = await self._s.execute(
            select(ProposalRecord)
            .where(ProposalRecord.status.in_(status_values))
            .order_by(ProposalRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self, proposal_id: str, status: ProposalStatus | str
    ) -> None:
        rec = await self.get(proposal_id)
        if rec:
            rec.status = status.value if isinstance(status, ProposalStatus) else status
            await self._s.commit()

    def to_proposal(self, record: ProposalRecord) -> Proposal:
        return Proposal(
            id=record.id,
            title=record.title,
            description=record.description,
            impact_pct=record.impact_pct,
            risk=record.risk,
            confidence_pct=record.confidence_pct,
            estimated_hours=record.estimated_hours,
            code_changes=record.code_changes or {},
            test_changes=record.test_changes or {},
            status=ProposalStatus(record.status),
            created_at=record.created_at,
            reference_claw=record.reference_claw,
        )


class AuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(
        self, action: str, detail: str = "", result: str = "ok", actor: str = "kinclaw"
    ) -> None:
        rec = AuditRecord(action=action, detail=detail, result=result, actor=actor)
        self._s.add(rec)
        await self._s.commit()


class ApprovalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_proposal_id(
        self, proposal_id: str
    ) -> ApprovalDecisionRecord | None:
        result = await self._s.execute(
            select(ApprovalDecisionRecord).where(
                ApprovalDecisionRecord.proposal_id == proposal_id
            )
        )
        return result.scalar_one_or_none()

    async def save_decision(self, approval: Approval) -> ApprovalDecisionRecord:
        rec = await self.get_by_proposal_id(approval.proposal_id)
        decision = "approved" if approval.approved else "rejected"
        if rec is None:
            rec = ApprovalDecisionRecord(
                proposal_id=approval.proposal_id,
                decision=decision,
                channel=approval.channel,
                raw_message=approval.raw_message,
                decided_at=approval.decided_at,
            )
            self._s.add(rec)
        else:
            rec.decision = decision
            rec.channel = approval.channel
            rec.raw_message = approval.raw_message
            rec.decided_at = approval.decided_at
        await self._s.commit()
        await self._s.refresh(rec)
        return rec

    async def delete_for_proposal(self, proposal_id: str) -> None:
        rec = await self.get_by_proposal_id(proposal_id)
        if rec is None:
            return
        await self._s.delete(rec)
        await self._s.commit()
