"""Data-access helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinclaw.core.types import Proposal, ProposalStatus
from kinclaw.database.models import AuditRecord, ProposalRecord


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


class AuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(
        self, action: str, detail: str = "", result: str = "ok", actor: str = "kinclaw"
    ) -> None:
        rec = AuditRecord(action=action, detail=detail, result=result, actor=actor)
        self._s.add(rec)
        await self._s.commit()
