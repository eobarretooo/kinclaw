"""Proposals API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/")
async def list_proposals(status: str | None = None):
    try:
        from kinclaw.database.connection import get_session
        from kinclaw.database.queries import ProposalRepo

        async with get_session() as session:
            repo = ProposalRepo(session)
            if status is None:
                results = await repo.list_by_statuses(["pending", "sent"])
            else:
                results = await repo.list_by_status(status)
        return [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "impact_pct": r.impact_pct,
                "risk": r.risk,
                "confidence_pct": r.confidence_pct,
                "created_at": r.created_at.isoformat(),
            }
            for r in results
        ]
    except RuntimeError:
        # DB not initialized (e.g. during testing without init_db)
        return []


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str):
    try:
        from kinclaw.database.connection import get_session
        from kinclaw.database.queries import ProposalRepo

        async with get_session() as session:
            repo = ProposalRepo(session)
            rec = await repo.get(proposal_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return {
            "id": rec.id,
            "title": rec.title,
            "description": rec.description,
            "status": rec.status,
            "impact_pct": rec.impact_pct,
            "risk": rec.risk,
            "confidence_pct": rec.confidence_pct,
            "estimated_hours": rec.estimated_hours,
            "created_at": rec.created_at.isoformat(),
        }
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not available")
