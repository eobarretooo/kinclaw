"""Click CLI commands for KinClaw."""
from __future__ import annotations

import asyncio
import click


@click.group()
def cli():
    """KinClaw — Autonomous Self-Improving AI Agent"""


@cli.command()
@click.option("--host", default=None, help="Web server host (overrides .env)")
@click.option("--port", default=None, type=int, help="Web server port (overrides .env)")
def run(host: str | None, port: int | None):
    """Start KinClaw agent + web dashboard."""
    import uvicorn
    import threading
    from kinclaw.config import get_settings
    from kinclaw.core.orchestrator import Orchestrator

    settings = get_settings()
    if host:
        object.__setattr__(settings, "web_host", host)
    if port:
        object.__setattr__(settings, "web_port", port)

    click.echo("🤖 Starting KinClaw...")

    # Start web server in background thread
    from kinclaw.web.app import app

    def run_web():
        uvicorn.run(app, host=settings.web_host, port=settings.web_port, log_level="warning")

    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    click.echo(f"📊 Dashboard: http://{settings.web_host}:{settings.web_port}")

    orchestrator = Orchestrator(settings=settings)
    asyncio.run(orchestrator.start())


@cli.command()
def status():
    """Show current agent status."""
    import httpx
    try:
        r = httpx.get("http://localhost:8000/api/status", timeout=3)
        data = r.json()
        click.echo(f"Status:  {data['status']}")
        click.echo(f"Phase:   {data.get('phase', 'unknown')}")
        click.echo(f"Proposals today: {data.get('proposals_today', 0)}")
    except Exception as e:
        click.echo(f"Could not connect to KinClaw: {e}", err=True)
        raise SystemExit(1)


@cli.command(name="proposals")
def list_proposals():
    """List pending proposals."""
    import httpx
    try:
        r = httpx.get("http://localhost:8000/api/proposals/", timeout=3)
        items = r.json()
        if not items:
            click.echo("No pending proposals.")
            return
        for p in items:
            click.echo(
                f"[{p['id'][:8]}] {p['title']}\n"
                f"         Risk: {p['risk']} | Impact: +{p['impact_pct']}% | "
                f"Confidence: {p['confidence_pct']}%"
            )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
