"""Dashboard overview route."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _templates.TemplateResponse("index.html", {"request": request})


def _serialize_proposal(record) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "status": record.status,
        "impact_pct": record.impact_pct,
        "risk": record.risk,
        "confidence_pct": record.confidence_pct,
        "created_at": record.created_at.isoformat(),
    }


async def _load_runtime_snapshot() -> dict:
    from kinclaw.web.app import get_agent_state

    state = get_agent_state().copy()
    metrics = state.get("last_analysis_metrics", {})
    proposals = []

    try:
        from kinclaw.database.connection import get_session
        from kinclaw.database.queries import ProposalRepo

        async with get_session() as session:
            repo = ProposalRepo(session)
            proposals = await repo.list_by_statuses(["pending", "sent"])
    except Exception:
        logger.warning(
            "Proposal loading failed while building runtime snapshot",
            exc_info=True,
        )
        proposals = []

    pending_count = sum(1 for proposal in proposals if proposal.status == "pending")
    sent_count = sum(1 for proposal in proposals if proposal.status == "sent")

    return {
        "status": "running" if state.get("is_running") else "idle",
        "version": "1.0.0",
        "name": "KinClaw",
        "files": metrics.get("files", 0),
        "lines": metrics.get("lines", 0),
        "proposal_summary": {
            "pending": pending_count,
            "sent": sent_count,
            "active_total": len(proposals),
        },
        "recent_proposals": [
            _serialize_proposal(proposal) for proposal in proposals[:5]
        ],
        **state,
    }


@router.get("/api/status")
async def status():
    return await _load_runtime_snapshot()


@router.get("/api/status/stream")
async def status_stream(
    request: Request,
    interval_ms: int = Query(default=15000, ge=1),
    max_events: int | None = Query(default=None, ge=1),
):
    async def event_stream():
        sent_events = 0
        while True:
            if await request.is_disconnected():
                break

            snapshot = await _load_runtime_snapshot()
            payload = json.dumps(snapshot, separators=(",", ":"))
            yield f"event: status\ndata: {payload}\n\n"
            sent_events += 1
            if max_events is not None and sent_events >= max_events:
                break
            yield ": keepalive\n\n"
            await asyncio.sleep(interval_ms / 1000)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
