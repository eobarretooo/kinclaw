"""Dashboard overview route."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/status")
async def status():
    from kinclaw.web.app import get_agent_state
    state = get_agent_state()
    return {
        "status": "running" if state.get("is_running") else "idle",
        "version": "1.0.0",
        "name": "KinClaw",
        **state,
    }
