"""Tests for the web/API layer using FastAPI TestClient."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kinclaw.database.connection import init_db, get_session
from kinclaw.database.queries import ProposalRepo
from kinclaw.web.app import set_agent_state


@pytest.fixture
def client():
    from kinclaw.web.app import app

    return TestClient(app)


def test_status_endpoint_returns_json(client):
    set_agent_state(
        {
            "is_running": True,
            "phase": "analyzing",
            "proposals_today": 2,
            "last_analysis_metrics": {"files": 11, "lines": 230},
        }
    )
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "name" in data
    assert data["name"] == "KinClaw"
    assert data["files"] == 11
    assert data["lines"] == 230


@pytest.mark.asyncio
async def test_status_endpoint_returns_runtime_snapshot_with_proposal_summary(client):
    await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="pending-runtime-proposal",
            title="Tighten dashboard refresh loop",
            description="reduce stale UI state",
            impact_pct=12,
            risk="low",
            confidence_pct=88,
            status="pending",
        )
        await repo.create(
            id="sent-runtime-proposal",
            title="Expose richer runtime snapshot",
            description="share live status details",
            impact_pct=9,
            risk="medium",
            confidence_pct=73,
            status="sent",
        )

    set_agent_state(
        {
            "is_running": True,
            "phase": "reviewing_proposals",
            "proposals_today": 4,
            "last_cycle_started_at": "2026-03-15T10:00:00Z",
            "last_analysis_metrics": {"files": 19, "lines": 640},
        }
    )

    resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["proposal_summary"] == {"pending": 1, "sent": 1, "active_total": 2}
    assert [proposal["id"] for proposal in data["recent_proposals"]] == [
        "sent-runtime-proposal",
        "pending-runtime-proposal",
    ]
    assert data["last_cycle_started_at"] == "2026-03-15T10:00:00Z"


def test_status_stream_endpoint_returns_sse_snapshot(client):
    set_agent_state(
        {
            "is_running": False,
            "phase": "idle",
            "proposals_today": 0,
            "last_analysis_metrics": {"files": 3, "lines": 42},
        }
    )

    with client.stream("GET", "/api/status/stream") as resp:
        chunks = []
        for chunk in resp.iter_text():
            if chunk:
                chunks.append(chunk)
            if "event: status" in "".join(chunks):
                break

    payload = "".join(chunks)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in payload
    assert '"status":"idle"' in payload
    assert '"files":3' in payload


def test_proposals_endpoint_returns_list(client):
    """Returns list (possibly empty if DB not initialized)."""
    resp = client.get("/api/proposals/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_proposals_endpoint_returns_persisted_pending_proposals(client):
    await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="web-proposal",
            title="Visible proposal",
            description="show me",
            impact_pct=15,
            risk="low",
            confidence_pct=77,
            status="pending",
        )

    resp = client.get("/api/proposals/")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == "web-proposal"
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_proposals_endpoint_default_list_includes_sent_proposals(client):
    await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="sent-proposal",
            title="Awaiting approval",
            description="already sent to owner",
            impact_pct=18,
            risk="low",
            confidence_pct=81,
            status="sent",
        )

    resp = client.get("/api/proposals/")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == "sent-proposal"
    assert data[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_proposals_endpoint_default_list_excludes_non_actionable_statuses(client):
    await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="timed-out-proposal",
            title="Timed out",
            description="no response",
            impact_pct=10,
            risk="low",
            confidence_pct=50,
            status="timed_out",
        )
        await repo.create(
            id="pr-failed-proposal",
            title="PR failed",
            description="needs attention",
            impact_pct=10,
            risk="low",
            confidence_pct=50,
            status="pr_failed",
        )

    resp = client.get("/api/proposals/")

    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "KinClaw" in resp.text
    assert "<!DOCTYPE html>" in resp.text
    assert "Live Runtime" in resp.text
    assert "proposal-summary" in resp.text


def test_repo_landing_page_uses_honest_runtime_copy():
    landing = (Path(__file__).resolve().parents[1] / "index.html").read_text(
        encoding="utf-8"
    )

    assert "47 dias" not in landing
    assert "v0.7.3" not in landing
    assert "PR #284" not in landing
    assert "live-status-value" in landing
    assert "Dados em tempo real aparecem aqui quando o dashboard esta ativo" in landing


def test_github_webhook_accepted(client):
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
