from click.testing import CliRunner

from kinclaw.cli.commands import cli


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_status_command_shows_live_analysis_metrics(monkeypatch):
    def fake_get(url, timeout):
        assert url.endswith("/api/status")
        return _Response(
            {
                "status": "running",
                "phase": "executing",
                "proposals_today": 3,
                "files": 14,
                "lines": 420,
            }
        )

    monkeypatch.setattr("httpx.get", fake_get)

    result = CliRunner().invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Files:   14" in result.output
    assert "Lines:   420" in result.output


def test_proposals_command_lists_pending_items_from_api(monkeypatch):
    def fake_get(url, timeout):
        assert url.endswith("/api/proposals/")
        return _Response(
            [
                {
                    "id": "proposal-1234",
                    "title": "Visible proposal",
                    "risk": "low",
                    "impact_pct": 15,
                    "confidence_pct": 88,
                    "status": "pending",
                }
            ]
        )

    monkeypatch.setattr("httpx.get", fake_get)

    result = CliRunner().invoke(cli, ["proposals"])

    assert result.exit_code == 0
    assert "Visible proposal" in result.output
    assert "proposal" in result.output.lower()
