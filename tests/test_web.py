"""Tests for the web/API layer using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from kinclaw.web.app import app
    return TestClient(app)


def test_status_endpoint_returns_json(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "name" in data
    assert data["name"] == "KinClaw"


def test_proposals_endpoint_returns_list(client):
    """Returns list (possibly empty if DB not initialized)."""
    resp = client.get("/api/proposals/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


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
