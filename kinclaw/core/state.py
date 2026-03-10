"""Agent state machine."""
from __future__ import annotations

from datetime import date
from enum import Enum


class AgentPhase(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    PROPOSING = "proposing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    REPORTING = "reporting"
    ERROR = "error"


class AgentState:
    def __init__(self) -> None:
        self.phase = AgentPhase.IDLE
        self.is_running = False
        self.proposals_today = 0
        self.proposals_date = date.today()
        self.current_proposal_id: str | None = None
        self.error: str | None = None

    def reset_daily_counters_if_new_day(self) -> None:
        today = date.today()
        if today != self.proposals_date:
            self.proposals_today = 0
            self.proposals_date = today

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "is_running": self.is_running,
            "proposals_today": self.proposals_today,
            "current_proposal_id": self.current_proposal_id,
            "error": self.error,
        }
