"""FastAPI web application — dashboard and webhook endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from kinclaw.web.routes import overview, proposals, webhooks

_BASE = Path(__file__).parent

app = FastAPI(title="KinClaw Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")

app.include_router(overview.router)
app.include_router(proposals.router, prefix="/api/proposals")
app.include_router(webhooks.router, prefix="/webhooks")

# Shared state injected at runtime by orchestrator
_agent_state: dict = {}


def set_agent_state(state_dict: dict) -> None:
    """Called by orchestrator to inject live agent state into the web layer."""
    global _agent_state
    _agent_state.update(state_dict)


def get_agent_state() -> dict:
    return _agent_state
