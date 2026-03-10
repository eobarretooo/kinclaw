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
    """Start KinClaw agent + web dashboard (same event loop)."""
    from kinclaw.config import get_settings
    from kinclaw.core.orchestrator import Orchestrator
    from kinclaw.logger import setup_logging

    setup_logging()
    settings = get_settings()
    web_host = host or settings.web_host
    web_port = port or settings.web_port

    click.echo("🤖 Starting KinClaw...")
    browser_host = "localhost" if web_host == "0.0.0.0" else web_host
    click.echo(f"📊 Dashboard: http://{browser_host}:{web_port}")

    async def _run_all():
        import uvicorn
        from kinclaw.web.app import app

        orchestrator = Orchestrator(settings=settings)

        web_config = uvicorn.Config(
            app, host=web_host, port=web_port,
            log_level="warning", loop="none",
        )
        web_server = uvicorn.Server(web_config)

        web_task = asyncio.create_task(web_server.serve())
        agent_task = asyncio.create_task(orchestrator.start())

        try:
            await asyncio.gather(web_task, agent_task)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            click.echo("\n🛑 Shutting down KinClaw...")
            await orchestrator.stop()
            web_server.should_exit = True
            # Wait briefly for tasks to finish
            for task in (web_task, agent_task):
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            click.echo("✅ KinClaw stopped.")

    try:
        asyncio.run(_run_all())
    except KeyboardInterrupt:
        pass


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
