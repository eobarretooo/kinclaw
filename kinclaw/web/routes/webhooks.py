"""Webhook endpoints for GitHub and channel callbacks."""
from __future__ import annotations

from fastapi import APIRouter, Request

from kinclaw.logger import logger

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request):
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "unknown")
    action = payload.get("action", "")
    logger.info("GitHub webhook: {} {}", event, action)

    # Handle PR merge events
    if event == "pull_request" and action == "closed" and payload.get("pull_request", {}).get("merged"):
        pr_number = payload["pull_request"]["number"]
        logger.info("PR #{} merged — triggering next cycle", pr_number)

    return {"received": True, "event": event}
