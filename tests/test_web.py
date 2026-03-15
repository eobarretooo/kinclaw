"""Tests for the web/API layer using FastAPI TestClient."""

import logging
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


@pytest.mark.asyncio
async def test_status_endpoint_reports_awaiting_approval_when_pending_proposals_exist(
    client,
):
    await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="awaiting-approval-proposal",
            title="Needs owner approval",
            description="still actionable",
            impact_pct=11,
            risk="low",
            confidence_pct=79,
            status="pending",
        )

    set_agent_state(
        {
            "is_running": False,
            "phase": "idle",
            "proposals_today": 1,
            "last_analysis_metrics": {"files": 6, "lines": 91},
        }
    )

    resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_approval"
    assert data["phase"] == "awaiting_approval"
    assert data["proposal_summary"] == {"pending": 1, "sent": 0, "active_total": 1}


def test_status_stream_endpoint_streams_multiple_sse_snapshots(client):
    import asyncio

    asyncio.run(init_db("sqlite+aiosqlite:///:memory:"))
    set_agent_state(
        {
            "is_running": False,
            "phase": "idle",
            "proposals_today": 0,
            "last_analysis_metrics": {"files": 3, "lines": 42},
        }
    )

    with client.stream("GET", "/api/status/stream?interval_ms=1&max_events=2") as resp:
        chunks = []
        for chunk in resp.iter_text():
            if chunk:
                chunks.append(chunk)
            if "".join(chunks).count("event: status") >= 2:
                break

    payload = "".join(chunks)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert payload.count("event: status") == 2
    assert '"status":"idle"' in payload
    assert '"files":3' in payload


@pytest.mark.asyncio
async def test_status_endpoint_returns_state_when_proposal_loading_fails_after_db_init(
    client, monkeypatch, caplog
):
    await init_db("sqlite+aiosqlite:///:memory:")
    set_agent_state(
        {
            "is_running": True,
            "phase": "analyzing",
            "proposals_today": 5,
            "last_analysis_metrics": {"files": 17, "lines": 510},
        }
    )

    async def raising_list_by_statuses(self, statuses):
        raise ValueError("database read failed")

    monkeypatch.setattr(ProposalRepo, "list_by_statuses", raising_list_by_statuses)

    caplog.set_level(logging.WARNING)

    resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["files"] == 17
    assert data["proposal_summary"] == {"pending": 0, "sent": 0, "active_total": 0}
    assert data["recent_proposals"] == []
    assert "Proposal loading failed while building runtime snapshot" in caplog.text


@pytest.mark.asyncio
async def test_status_stream_returns_state_when_proposal_loading_fails_after_db_init(
    client, monkeypatch, caplog
):
    await init_db("sqlite+aiosqlite:///:memory:")
    set_agent_state(
        {
            "is_running": False,
            "phase": "idle",
            "proposals_today": 0,
            "last_analysis_metrics": {"files": 9, "lines": 81},
        }
    )

    async def raising_list_by_statuses(self, statuses):
        raise ValueError("database read failed")

    monkeypatch.setattr(ProposalRepo, "list_by_statuses", raising_list_by_statuses)

    caplog.set_level(logging.WARNING)

    with client.stream("GET", "/api/status/stream?interval_ms=1&max_events=1") as resp:
        payload = "".join(chunk for chunk in resp.iter_text() if chunk)

    assert resp.status_code == 200
    assert '"status":"idle"' in payload
    assert '"proposal_summary":{"pending":0,"sent":0,"active_total":0}' in payload
    assert '"recent_proposals":[]' in payload
    assert "Proposal loading failed while building runtime snapshot" in caplog.text


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
    assert "new EventSource('/api/status/stream')" in landing
    assert "fetch('/api/status')" in landing
    assert "runtime-status-note" in landing
    assert "liveProposalsValue.textContent = '--'" in landing
    assert "liveFilesValue.textContent = '--'" in landing
    assert "liveLinesValue.textContent = '--'" in landing
    assert "liveStatusValue.textContent = 'aguardando'" in landing


def test_dashboard_js_clears_runtime_values_when_fallback_triggers():
    dashboard_js = (
        Path(__file__).resolve().parents[1]
        / "kinclaw"
        / "web"
        / "static"
        / "dashboard.js"
    ).read_text(encoding="utf-8")

    assert "function clearDashboardFallback()" in dashboard_js
    assert "setText('stat-phase', 'idle')" in dashboard_js
    assert "setText('stat-cycle', 'Not reported')" in dashboard_js
    assert "setText('stat-proposals', '0')" in dashboard_js
    assert "setText('stat-files', '0')" in dashboard_js
    assert "setText('stat-lines', '0')" in dashboard_js
    assert "setText('stat-active-proposals', '0')" in dashboard_js
    assert (
        'list.innerHTML = \'<p class="empty-msg">Live runtime data is temporarily unavailable.'
        in dashboard_js
    )


def test_github_webhook_accepted(client):
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
