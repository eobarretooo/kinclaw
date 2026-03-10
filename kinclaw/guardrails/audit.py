"""Audit log wrapper around the database."""
from __future__ import annotations

from kinclaw.logger import logger


class AuditLogger:
    """Logs all significant KinClaw actions for human review."""

    async def log(
        self,
        action: str,
        detail: str = "",
        result: str = "ok",
        actor: str = "kinclaw",
    ) -> None:
        try:
            from kinclaw.database.connection import get_session
            from kinclaw.database.queries import AuditRepo
            async with get_session() as session:
                repo = AuditRepo(session)
                await repo.log(action=action, detail=detail, result=result, actor=actor)
        except Exception:
            logger.warning("Audit DB unavailable, logging to file only: {} {} {}", actor, action, result)
        logger.info("[AUDIT] {} | {} | {} | {}", actor, action, result, detail[:100])
