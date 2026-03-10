"""Core data-transfer types for KinClaw."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"


class OutboundMessage(BaseModel):
    channel: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime = Field(default_factory=datetime.utcnow)


class ProposalStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"


class Proposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    impact_pct: int = 0
    risk: str = "low"
    confidence_pct: int = 0
    estimated_hours: float = 1.0
    code_changes: dict[str, str] = Field(default_factory=dict)
    test_changes: dict[str, str] = Field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference_claw: str = ""


class Approval(BaseModel):
    proposal_id: str
    approved: bool
    channel: str
    raw_message: str
    decided_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisMetrics(BaseModel):
    lines_of_code: int = 0
    num_files: int = 0
    test_coverage_pct: float = 0.0
    complexity_avg: float = 0.0
    security_issues: int = 0


class SelfAnalysis(BaseModel):
    metrics: AnalysisMetrics
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
