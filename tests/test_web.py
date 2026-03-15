"""Tests for the web/API layer using FastAPI TestClient."""

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


def test_dashboard_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "KinClaw" in resp.text
    assert "<!DOCTYPE html>" in resp.text


def test_github_webhook_accepted(client):
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
