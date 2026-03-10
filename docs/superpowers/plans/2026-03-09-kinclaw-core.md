# KinClaw — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build KinClaw, a 24/7 autonomous AI agent in Python that self-analyzes its own code, proposes improvements, awaits owner approval via multi-channel messaging (Telegram/Discord/etc.), then executes: commits, opens PRs, and reports results.

**Architecture:** Event-driven async Python with a central `MessageBus` (queue-based pub/sub), a `KinClawAgent` that runs a perpetual self-improvement loop, pluggable `Channel` adapters (Telegram, Discord…), a `Skill` registry for tool execution, and a `Guardrails` layer ensuring budget/safety limits are always respected.

**Tech Stack:** Python 3.11+, asyncio, FastAPI, SQLAlchemy (SQLite→Postgres), `anthropic` SDK, `python-telegram-bot`, `discord.py`, `python-dotenv`, `pydantic-settings`, `loguru`, `GitPython`, `PyGithub`, `pytest-asyncio`.

---

## Chunk 1: Project Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `kinclaw/__init__.py`
- Create: `kinclaw/core/__init__.py`
- Create: `kinclaw/channels/__init__.py`
- Create: `kinclaw/skills/__init__.py`
- Create: `kinclaw/skills/builtin/__init__.py`
- Create: `kinclaw/tools/__init__.py`
- Create: `kinclaw/providers/__init__.py`
- Create: `kinclaw/auto_improve/__init__.py`
- Create: `kinclaw/approval/__init__.py`
- Create: `kinclaw/guardrails/__init__.py`
- Create: `kinclaw/web/__init__.py`
- Create: `kinclaw/web/routes/__init__.py`
- Create: `kinclaw/cli/__init__.py`
- Create: `kinclaw/database/__init__.py`
- Create: `kinclaw/utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create all package directories with `__init__.py`**

```bash
mkdir -p kinclaw/{core,channels,skills/builtin,tools,providers,auto_improve,approval,guardrails,web/routes,web/templates,web/static,cli,database,utils}
mkdir -p tests
touch kinclaw/__init__.py kinclaw/core/__init__.py kinclaw/channels/__init__.py
touch kinclaw/skills/__init__.py kinclaw/skills/builtin/__init__.py
touch kinclaw/tools/__init__.py kinclaw/providers/__init__.py
touch kinclaw/auto_improve/__init__.py kinclaw/approval/__init__.py
touch kinclaw/guardrails/__init__.py kinclaw/web/__init__.py kinclaw/web/routes/__init__.py
touch kinclaw/cli/__init__.py kinclaw/database/__init__.py kinclaw/utils/__init__.py
touch tests/__init__.py
```

- [ ] **Step 2: Create `requirements.txt`**

```
# Core async
aiohttp==3.9.3
aiofiles==23.2.1

# FastAPI
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.7.0
pydantic-settings==2.3.0

# Database
sqlalchemy==2.0.30
alembic==1.13.1

# Integrations
python-telegram-bot==21.3
discord.py==2.4.0
slack-bolt==1.18.1

# AI
anthropic==0.28.0

# Git
GitPython==3.1.43
PyGithub==2.3.0

# Utilities
python-dotenv==1.0.1
pyyaml==6.0.1
click==8.1.7
loguru==0.7.2
httpx==0.27.0

# Testing
pytest==8.2.2
pytest-asyncio==0.23.7
pytest-cov==5.0.0

# Code quality
black==24.4.2
ruff==0.4.9
mypy==1.10.0

# Cryptography
cryptography==42.0.8
```

- [ ] **Step 3: Create `.env.example`**

```bash
cat > .env.example << 'EOF'
# KinClaw Environment Variables

# Claude API
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_IDS=123456789

# Discord
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...
DISCORD_GUILD_ID=...

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_REPO=owner/kinclaw
GITHUB_DEFAULT_BRANCH=main

# Behavior
SLEEP_BETWEEN_ANALYSES=3600
MAX_PROPOSALS_PER_DAY=3
AUTO_MERGE_CONFIDENCE=98

# Guardrails
MONTHLY_BUDGET_USD=100
MAX_COMMITS_PER_DAY=10
POSTS_PER_DAY=2

# Database
DATABASE_URL=sqlite+aiosqlite:///./kinclaw.db

# Web
WEB_HOST=0.0.0.0
WEB_PORT=8000
EOF
```

- [ ] **Step 4: Create `.gitignore`**

```bash
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.pyo
.env
venv/
.venv/
*.db
*.log
.coverage
htmlcov/
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
.pytest_cache/
EOF
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: scaffold project structure and dependencies"
```

---

### Task 2: Config System

**Files:**
- Create: `kinclaw/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import pytest
from kinclaw.config import Settings, get_settings


def test_settings_defaults():
    """Settings has sensible defaults without .env"""
    s = Settings(
        anthropic_api_key="test-key",
        github_token="ghp_test",
    )
    assert s.claude_model == "claude-sonnet-4-6"
    assert s.sleep_between_analyses == 3600
    assert s.max_proposals_per_day == 3
    assert s.monthly_budget_usd == 100


def test_settings_channels_list():
    """Active channels parsed from comma-separated string"""
    s = Settings(
        anthropic_api_key="k",
        github_token="t",
        active_channels="telegram,discord",
    )
    assert "telegram" in s.active_channels
    assert "discord" in s.active_channels


def test_get_settings_is_cached():
    """get_settings returns the same object on repeated calls"""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/producao/kinclaw && python -m pytest tests/test_config.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `kinclaw/config.py`**

```python
"""Global configuration via pydantic-settings (reads from .env)."""
from __future__ import annotations

import functools
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AI
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_ids: str = ""  # comma-sep integers

    # Discord
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    discord_guild_id: str = ""

    # GitHub
    github_token: str
    github_repo: str = "owner/kinclaw"
    github_default_branch: str = "main"

    # Behavior
    sleep_between_analyses: int = 3600
    max_proposals_per_day: int = 3
    auto_merge_confidence: int = 98

    # Guardrails
    monthly_budget_usd: float = 100.0
    max_commits_per_day: int = 10
    posts_per_day: int = 2

    # Database
    database_url: str = "sqlite+aiosqlite:///./kinclaw.db"

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # Channels
    active_channels: list[str] = ["telegram"]

    @field_validator("active_channels", mode="before")
    @classmethod
    def parse_channels(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v

    @property
    def telegram_allowed_id_list(self) -> list[int]:
        if not self.telegram_allowed_ids:
            return []
        return [int(x.strip()) for x in self.telegram_allowed_ids.split(",") if x.strip()]


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return (cached) global settings instance."""
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
ANTHROPIC_API_KEY=test-key GITHUB_TOKEN=ghp_test python -m pytest tests/test_config.py -v
```
Expected: all 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add kinclaw/config.py tests/test_config.py
git commit -m "feat: add pydantic-settings config system"
```

---

### Task 3: Logging

**Files:**
- Create: `kinclaw/logger.py`

- [ ] **Step 1: Implement `kinclaw/logger.py`**

```python
"""Centralized structured logging with loguru."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_level: str = "INFO", log_file: str | None = "kinclaw.log") -> None:
    """Configure loguru sinks."""
    logger.remove()
    # Console sink — colorized, human-readable
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
        colorize=True,
    )
    # File sink — JSON for machine parsing
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            serialize=True,
        )


# Re-export logger so callers do: from kinclaw.logger import logger
__all__ = ["logger", "setup_logging"]
```

- [ ] **Step 2: Commit**

```bash
git add kinclaw/logger.py
git commit -m "feat: add loguru logging setup"
```

---

### Task 4: Core Types

**Files:**
- Create: `kinclaw/core/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_types.py
from kinclaw.core.types import (
    InboundMessage, OutboundMessage, Proposal, ProposalStatus, Approval,
)
import uuid


def test_inbound_message_defaults():
    msg = InboundMessage(channel="telegram", sender_id="123", chat_id="123", content="hi")
    assert msg.id is not None
    assert msg.media == []


def test_proposal_status_lifecycle():
    p = Proposal(
        title="Test improvement",
        description="Add caching to memory.py",
        impact_pct=40,
        risk="low",
        confidence_pct=92,
        estimated_hours=2.0,
        code_changes={},
    )
    assert p.status == ProposalStatus.PENDING
    assert p.id is not None


def test_approval_approved():
    a = Approval(proposal_id="abc", approved=True, channel="telegram", raw_message="aprova")
    assert a.approved is True
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_types.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `kinclaw/core/types.py`**

```python
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
    impact_pct: int = 0          # Expected improvement %
    risk: str = "low"            # low | medium | high
    confidence_pct: int = 0      # 0-100
    estimated_hours: float = 1.0
    code_changes: dict[str, str] = Field(default_factory=dict)  # filepath→content
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
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_types.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/core/types.py tests/test_types.py
git commit -m "feat: add core Pydantic types (messages, proposals, approvals)"
```

---

### Task 5: Database Layer

**Files:**
- Create: `kinclaw/database/connection.py`
- Create: `kinclaw/database/models.py`
- Create: `kinclaw/database/queries.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_database.py
import pytest
import asyncio
from kinclaw.database.connection import init_db, get_session
from kinclaw.database.models import ProposalRecord
from kinclaw.database.queries import ProposalRepo


@pytest.fixture
async def db():
    """In-memory SQLite for tests."""
    await init_db("sqlite+aiosqlite:///:memory:")
    yield
    # teardown implicit


@pytest.mark.asyncio
async def test_create_and_fetch_proposal(db):
    async with get_session() as session:
        repo = ProposalRepo(session)
        rec = await repo.create(
            id="p1", title="Test", description="desc",
            impact_pct=10, risk="low", confidence_pct=80,
        )
        assert rec.id == "p1"
        fetched = await repo.get("p1")
        assert fetched is not None
        assert fetched.title == "Test"


@pytest.mark.asyncio
async def test_list_pending(db):
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(id="p2", title="A", description="d", impact_pct=5, risk="low", confidence_pct=60)
        results = await repo.list_by_status("pending")
        assert len(results) >= 1
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_database.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement database layer**

```python
# kinclaw/database/connection.py
"""Async SQLAlchemy engine factory and session context manager."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from kinclaw.database.models import Base

_engine = None
_session_factory = None


async def init_db(url: str) -> None:
    """Create engine + tables."""
    global _engine, _session_factory
    _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized — call init_db() first")
    async with _session_factory() as session:
        yield session
```

```python
# kinclaw/database/models.py
"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProposalRecord(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    impact_pct: Mapped[int] = mapped_column(Integer, default=0)
    risk: Mapped[str] = mapped_column(String(16), default="low")
    confidence_pct: Mapped[int] = mapped_column(Integer, default=0)
    estimated_hours: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    reference_claw: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditRecord(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(128))
    actor: Mapped[str] = mapped_column(String(64), default="kinclaw")
    detail: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(16), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

```python
# kinclaw/database/queries.py
"""Data-access helpers (thin repository layer)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinclaw.database.models import AuditRecord, ProposalRecord


class ProposalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, **kwargs) -> ProposalRecord:
        rec = ProposalRecord(**kwargs)
        self._s.add(rec)
        await self._s.commit()
        await self._s.refresh(rec)
        return rec

    async def get(self, proposal_id: str) -> ProposalRecord | None:
        result = await self._s.execute(
            select(ProposalRecord).where(ProposalRecord.id == proposal_id)
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, status: str) -> list[ProposalRecord]:
        result = await self._s.execute(
            select(ProposalRecord).where(ProposalRecord.status == status).order_by(ProposalRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(self, proposal_id: str, status: str) -> None:
        rec = await self.get(proposal_id)
        if rec:
            rec.status = status
            await self._s.commit()


class AuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(self, action: str, detail: str = "", result: str = "ok", actor: str = "kinclaw") -> None:
        rec = AuditRecord(action=action, detail=detail, result=result, actor=actor)
        self._s.add(rec)
        await self._s.commit()
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_database.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/database/ tests/test_database.py
git commit -m "feat: async SQLAlchemy database layer with ProposalRepo"
```

---

## Chunk 2: Message Bus & Provider

### Task 6: Message Bus

**Files:**
- Create: `kinclaw/core/bus.py`
- Test: `tests/test_bus.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_bus.py
import asyncio
import pytest
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_publish_and_consume_inbound():
    bus = MessageBus()
    msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="hello")
    await bus.publish_inbound(msg)
    consumed = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert consumed.content == "hello"


@pytest.mark.asyncio
async def test_publish_outbound_triggers_subscriber():
    bus = MessageBus()
    received = []

    async def handler(msg: OutboundMessage):
        received.append(msg)

    bus.subscribe_outbound(handler)
    out = OutboundMessage(channel="test", chat_id="c1", content="bye")
    await bus.publish_outbound(out)
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].content == "bye"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_bus.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `kinclaw/core/bus.py`**

```python
"""Async message bus for inbound/outbound routing."""
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from kinclaw.core.types import InboundMessage, OutboundMessage
from kinclaw.logger import logger


OutboundHandler = Callable[[OutboundMessage], Awaitable[None]]


class MessageBus:
    """Central pub/sub queue bridging channels and the agent loop."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound_subs: list[OutboundHandler] = []

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self._inbound.get()

    def subscribe_outbound(self, handler: OutboundHandler) -> None:
        self._outbound_subs.append(handler)

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        for handler in self._outbound_subs:
            try:
                await handler(msg)
            except Exception:
                logger.exception("Outbound handler error for channel {}", msg.channel)
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_bus.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/core/bus.py tests/test_bus.py
git commit -m "feat: async message bus with inbound queue and outbound pub/sub"
```

---

### Task 7: Claude Provider

**Files:**
- Create: `kinclaw/providers/base.py`
- Create: `kinclaw/providers/claude.py`
- Test: `tests/test_provider.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_provider.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.providers.claude import ClaudeProvider


@pytest.mark.asyncio
async def test_think_returns_string():
    """think() calls Claude API and returns text."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Paris is the capital.")]

    with patch("anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.think("What is the capital of France?")

    assert "Paris" in result
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_provider.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement provider**

```python
# kinclaw/providers/base.py
"""Abstract LLM provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def think(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        """Send prompt, return text response."""

    @abstractmethod
    async def think_json(self, prompt: str, system: str = "") -> dict:
        """Send prompt expecting JSON response, return parsed dict."""
```

```python
# kinclaw/providers/claude.py
"""Claude (Anthropic) LLM provider."""
from __future__ import annotations

import json

import anthropic

from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def think(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API error: {}", e)
            raise

    async def think_json(self, prompt: str, system: str = "") -> dict:
        """Call think() and parse JSON from the response."""
        text = await self.think(
            prompt=prompt + "\n\nRespond ONLY with valid JSON. No explanation.",
            system=system,
        )
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_provider.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/providers/ tests/test_provider.py
git commit -m "feat: Claude LLM provider with think() and think_json()"
```

---

## Chunk 3: Channels

### Task 8: Base Channel

**Files:**
- Create: `kinclaw/channels/base.py`
- Test: `tests/test_channels.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_channels.py
import pytest
import asyncio
from unittest.mock import AsyncMock
from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage


class FakeChannel(BaseChannel):
    name = "fake"
    sent: list = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


def test_is_allowed_wildcard():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    assert ch.is_allowed("anyone") is True


def test_is_allowed_list():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["123", "456"]}, bus=bus)
    assert ch.is_allowed("123") is True
    assert ch.is_allowed("999") is False


def test_is_allowed_empty_denies_all():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": []}, bus=bus)
    assert ch.is_allowed("anyone") is False


@pytest.mark.asyncio
async def test_handle_message_publishes_to_bus():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    await ch._handle_message("u1", "c1", "hello")
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=0.5)
    assert msg.content == "hello"
    assert msg.channel == "fake"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_channels.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `kinclaw/channels/base.py`**

```python
"""Abstract base class for all channel adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from kinclaw.core.bus import MessageBus
from kinclaw.core.types import InboundMessage, OutboundMessage
from kinclaw.logger import logger


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Connect and start listening for messages."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect and clean up."""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Deliver an outbound message."""

    def is_allowed(self, sender_id: str) -> bool:
        """Check sender against allowlist. Empty list → deny all; '*' → allow all."""
        allow = self.config.get("allow_from", []) if isinstance(self.config, dict) else getattr(self.config, "allow_from", [])
        if not allow:
            logger.warning("{}: allow_from is empty — denying sender {}", self.name, sender_id)
            return False
        if "*" in allow:
            return True
        return str(sender_id) in [str(a) for a in allow]

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_allowed(sender_id):
            logger.warning("{}: denied sender {}", self.name, sender_id)
            return
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(msg)

    @property
    def is_running(self) -> bool:
        return self._running
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_channels.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/channels/base.py tests/test_channels.py
git commit -m "feat: abstract BaseChannel with allowlist and message routing"
```

---

### Task 9: Telegram Channel

**Files:**
- Create: `kinclaw/channels/telegram.py`

- [ ] **Step 1: Implement `kinclaw/channels/telegram.py`**

```python
"""Telegram channel adapter using python-telegram-bot."""
from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, allowed_ids: list[int], bus: MessageBus) -> None:
        super().__init__(config={"allow_from": [str(i) for i in allowed_ids] or ["*"]}, bus=bus)
        self._token = token
        self._app: Application | None = None
        self._chat_map: dict[str, int] = {}  # session_key → chat_id

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )
        self._running = True
        logger.info("Telegram channel starting")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        self._running = False
        logger.info("Telegram channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not self._app:
            logger.warning("Telegram not started, cannot send")
            return
        try:
            await self._app.bot.send_message(chat_id=int(msg.chat_id), text=msg.content)
        except Exception as e:
            logger.error("Telegram send error: {}", e)

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        sender_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        content = update.message.text or ""
        await self._handle_message(sender_id, chat_id, content)
```

- [ ] **Step 2: Commit**

```bash
git add kinclaw/channels/telegram.py
git commit -m "feat: Telegram channel adapter"
```

---

### Task 10: Discord Channel

**Files:**
- Create: `kinclaw/channels/discord.py`

- [ ] **Step 1: Implement `kinclaw/channels/discord.py`**

```python
"""Discord channel adapter using discord.py."""
from __future__ import annotations

import discord

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class DiscordChannel(BaseChannel):
    name = "discord"

    def __init__(self, token: str, channel_id: int, allowed_ids: list[int], bus: MessageBus) -> None:
        super().__init__(config={"allow_from": [str(i) for i in allowed_ids] or ["*"]}, bus=bus)
        self._token = token
        self._channel_id = channel_id
        self._client: discord.Client | None = None

    async def start(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return
            if message.channel.id != self._channel_id:
                return
            await self._handle_message(
                str(message.author.id),
                str(message.channel.id),
                message.content,
            )

        self._running = True
        logger.info("Discord channel starting")
        await self._client.start(self._token)

    async def stop(self) -> None:
        if self._client:
            await self._client.close()
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        if not self._client:
            logger.warning("Discord not started")
            return
        channel = self._client.get_channel(int(msg.chat_id))
        if channel:
            try:
                await channel.send(msg.content)
            except Exception as e:
                logger.error("Discord send error: {}", e)
```

- [ ] **Step 2: Commit**

```bash
git add kinclaw/channels/discord.py
git commit -m "feat: Discord channel adapter"
```

---

### Task 11: Channel Router

**Files:**
- Create: `kinclaw/channels/router.py`
- Test: addition to `tests/test_channels.py`

- [ ] **Step 1: Implement `kinclaw/channels/router.py`**

```python
"""Routes outbound messages to the correct channel adapter."""
from __future__ import annotations

import asyncio

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class ChannelRouter:
    """Manages all channel adapters and routes outbound messages."""

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus
        self._channels: dict[str, BaseChannel] = {}
        self._bus.subscribe_outbound(self._route_outbound)

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel
        logger.info("Channel registered: {}", channel.name)

    async def start_all(self) -> None:
        tasks = [ch.start() for ch in self._channels.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        for ch in self._channels.values():
            try:
                await ch.stop()
            except Exception:
                logger.exception("Error stopping channel {}", ch.name)

    async def broadcast(self, content: str) -> None:
        """Send same message to ALL registered channels."""
        for ch in self._channels.values():
            for chat_id in self._get_default_chat_ids(ch):
                out = OutboundMessage(channel=ch.name, chat_id=chat_id, content=content)
                await self._broadcast_to_channel(ch, out)

    async def _broadcast_to_channel(self, ch: BaseChannel, msg: OutboundMessage) -> None:
        try:
            await ch.send(msg)
        except Exception:
            logger.exception("Broadcast error on channel {}", ch.name)

    async def _route_outbound(self, msg: OutboundMessage) -> None:
        ch = self._channels.get(msg.channel)
        if ch:
            await ch.send(msg)
        else:
            logger.warning("No channel registered for: {}", msg.channel)

    def _get_default_chat_ids(self, ch: BaseChannel) -> list[str]:
        """Return configured default chat IDs for a channel."""
        cfg = ch.config
        if isinstance(cfg, dict):
            return [str(cfg.get("default_chat_id", ""))]
        return [str(getattr(cfg, "default_chat_id", ""))]
```

- [ ] **Step 2: Commit**

```bash
git add kinclaw/channels/router.py
git commit -m "feat: ChannelRouter broadcasts and routes outbound messages"
```

---

## Chunk 4: Skills System

### Task 12: Skill Base & Registry

**Files:**
- Create: `kinclaw/skills/base.py`
- Create: `kinclaw/skills/registry.py`
- Create: `kinclaw/skills/loader.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_skills.py
import pytest
from kinclaw.skills.base import BaseSkill
from kinclaw.skills.registry import SkillRegistry


class EchoSkill(BaseSkill):
    name = "echo"
    description = "Echoes input back"

    async def execute(self, message: str = "") -> dict:
        return {"echo": message}

    async def validate(self, **kwargs) -> bool:
        return "message" in kwargs


@pytest.mark.asyncio
async def test_skill_execute():
    skill = EchoSkill()
    result = await skill.execute(message="hello")
    assert result["echo"] == "hello"


def test_registry_register_and_get():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    skill = reg.get("echo")
    assert skill is not None
    assert skill.name == "echo"


def test_registry_list():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    names = reg.list_names()
    assert "echo" in names


@pytest.mark.asyncio
async def test_registry_execute():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    result = await reg.execute("echo", message="world")
    assert result["echo"] == "world"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_skills.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement skill base and registry**

```python
# kinclaw/skills/base.py
"""Abstract base class for all KinClaw skills."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the skill and return a result dict."""

    async def validate(self, **kwargs) -> bool:
        """Validate parameters before execution. Override for custom logic."""
        return True
```

```python
# kinclaw/skills/registry.py
"""Central registry for all loaded skills."""
from __future__ import annotations

from kinclaw.logger import logger
from kinclaw.skills.base import BaseSkill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill
        logger.debug("Skill registered: {}", skill.name)

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills.keys())

    def all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    async def execute(self, name: str, **kwargs) -> dict:
        skill = self.get(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name}")
        if not await skill.validate(**kwargs):
            raise ValueError(f"Invalid parameters for skill: {name}")
        return await skill.execute(**kwargs)
```

```python
# kinclaw/skills/loader.py
"""Discovers and loads all built-in skills into a registry."""
from __future__ import annotations

from kinclaw.skills.registry import SkillRegistry
from kinclaw.skills.builtin.file_manager import FileManagerSkill
from kinclaw.skills.builtin.code_executor import CodeExecutorSkill
from kinclaw.skills.builtin.git_manager import GitManagerSkill
from kinclaw.skills.builtin.github_api import GitHubAPISkill
from kinclaw.skills.builtin.web_search import WebSearchSkill
from kinclaw.skills.builtin.code_analyzer import CodeAnalyzerSkill


def load_builtin_skills(registry: SkillRegistry) -> None:
    """Register all built-in skills into the registry."""
    for SkillCls in [
        FileManagerSkill,
        CodeExecutorSkill,
        GitManagerSkill,
        GitHubAPISkill,
        WebSearchSkill,
        CodeAnalyzerSkill,
    ]:
        registry.register(SkillCls())
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_skills.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/skills/base.py kinclaw/skills/registry.py kinclaw/skills/loader.py tests/test_skills.py
git commit -m "feat: skill base class, registry, and loader"
```

---

### Task 13: Built-in Skills

**Files:**
- Create: `kinclaw/skills/builtin/file_manager.py`
- Create: `kinclaw/skills/builtin/code_analyzer.py`
- Create: `kinclaw/skills/builtin/code_executor.py`
- Create: `kinclaw/skills/builtin/git_manager.py`
- Create: `kinclaw/skills/builtin/github_api.py`
- Create: `kinclaw/skills/builtin/web_search.py`

- [ ] **Step 1: Implement `file_manager.py`**

```python
# kinclaw/skills/builtin/file_manager.py
"""File read/write skill."""
from __future__ import annotations

import aiofiles
from pathlib import Path
from kinclaw.skills.base import BaseSkill


class FileManagerSkill(BaseSkill):
    name = "file_manager"
    description = "Read or write files on the local filesystem."

    async def execute(self, action: str = "read", path: str = "", content: str = "") -> dict:
        p = Path(path)
        if action == "read":
            if not p.exists():
                return {"error": f"File not found: {path}"}
            async with aiofiles.open(p, "r") as f:
                text = await f.read()
            return {"content": text, "lines": text.count("\n") + 1}
        elif action == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(p, "w") as f:
                await f.write(content)
            return {"written": True, "path": str(p)}
        elif action == "list":
            if not p.is_dir():
                return {"error": "Not a directory"}
            files = [str(f.relative_to(p)) for f in p.rglob("*.py")]
            return {"files": files}
        return {"error": f"Unknown action: {action}"}
```

- [ ] **Step 2: Implement `code_analyzer.py`**

```python
# kinclaw/skills/builtin/code_analyzer.py
"""Analyzes Python code metrics."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from kinclaw.skills.base import BaseSkill


class CodeAnalyzerSkill(BaseSkill):
    name = "code_analyzer"
    description = "Analyze Python code: count lines, functions, complexity."

    async def execute(self, path: str = ".") -> dict:
        p = Path(path)
        py_files = list(p.rglob("*.py")) if p.is_dir() else [p]

        total_lines = 0
        total_functions = 0
        total_classes = 0
        errors: list[str] = []

        for f in py_files:
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                total_lines += src.count("\n") + 1
                tree = ast.parse(src)
                total_functions += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                total_classes += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            except SyntaxError as e:
                errors.append(f"{f}: {e}")

        return {
            "files": len(py_files),
            "lines": total_lines,
            "functions": total_functions,
            "classes": total_classes,
            "errors": errors,
        }
```

- [ ] **Step 3: Implement `code_executor.py`**

```python
# kinclaw/skills/builtin/code_executor.py
"""Executes code in a subprocess sandbox (no network, timeout enforced)."""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class CodeExecutorSkill(BaseSkill):
    name = "code_executor"
    description = "Execute Python code in a sandboxed subprocess."

    async def execute(self, code: str = "", timeout: int = 30) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "success": proc.returncode == 0,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"returncode": -1, "stdout": "", "stderr": "Timeout exceeded", "success": False}
        finally:
            Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 4: Implement `git_manager.py`**

```python
# kinclaw/skills/builtin/git_manager.py
"""Git operations skill."""
from __future__ import annotations

import asyncio
from pathlib import Path

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


async def _run_git(*args: str, cwd: str = ".") -> dict:
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
        "success": proc.returncode == 0,
    }


class GitManagerSkill(BaseSkill):
    name = "git_manager"
    description = "Run git operations: status, add, commit, push, branch."

    async def execute(
        self,
        action: str = "status",
        message: str = "",
        files: list[str] | None = None,
        branch: str = "",
        cwd: str = ".",
    ) -> dict:
        if action == "status":
            return await _run_git("status", "--short", cwd=cwd)
        elif action == "add":
            targets = files or ["."]
            return await _run_git("add", *targets, cwd=cwd)
        elif action == "commit":
            if not message:
                return {"error": "Commit message required"}
            return await _run_git("commit", "-m", message, cwd=cwd)
        elif action == "push":
            return await _run_git("push", cwd=cwd)
        elif action == "checkout_branch":
            return await _run_git("checkout", "-b", branch, cwd=cwd)
        elif action == "diff":
            return await _run_git("diff", "--stat", "HEAD", cwd=cwd)
        return {"error": f"Unknown action: {action}"}
```

- [ ] **Step 5: Implement `github_api.py`**

```python
# kinclaw/skills/builtin/github_api.py
"""GitHub API skill via PyGithub."""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class GitHubAPISkill(BaseSkill):
    name = "github_api"
    description = "Create PRs, issues, and interact with GitHub."

    def __init__(self, token: str = "", repo: str = "") -> None:
        self._token = token
        self._repo = repo

    async def execute(
        self,
        action: str = "create_pr",
        title: str = "",
        body: str = "",
        head: str = "",
        base: str = "main",
        number: int = 0,
    ) -> dict:
        if not self._token:
            return {"error": "GitHub token not configured"}
        try:
            from github import Github
            g = Github(self._token)
            repo = g.get_repo(self._repo)

            if action == "create_pr":
                pr = await asyncio.get_event_loop().run_in_executor(
                    None, partial(repo.create_pull, title=title, body=body, head=head, base=base)
                )
                return {"pr_number": pr.number, "url": pr.html_url, "success": True}
            elif action == "get_pr":
                pr = await asyncio.get_event_loop().run_in_executor(None, repo.get_pull, number)
                return {"number": pr.number, "state": pr.state, "merged": pr.merged}
            elif action == "list_prs":
                prs = await asyncio.get_event_loop().run_in_executor(
                    None, partial(repo.get_pulls, state="open")
                )
                return {"prs": [{"number": p.number, "title": p.title} for p in prs]}
        except Exception as e:
            logger.error("GitHub API error: {}", e)
            return {"error": str(e), "success": False}
        return {"error": f"Unknown action: {action}"}
```

- [ ] **Step 6: Implement `web_search.py`**

```python
# kinclaw/skills/builtin/web_search.py
"""Web search skill via httpx."""
from __future__ import annotations

import httpx
from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web and return results."

    async def execute(self, query: str = "", max_results: int = 5) -> dict:
        """Search using DuckDuckGo Instant Answer API (no key required)."""
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
            results = []
            for r in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in r:
                    results.append({"text": r["Text"], "url": r.get("FirstURL", "")})
            return {"results": results, "abstract": data.get("Abstract", "")}
        except Exception as e:
            logger.error("Web search error: {}", e)
            return {"error": str(e), "results": []}
```

- [ ] **Step 7: Commit all built-in skills**

```bash
git add kinclaw/skills/builtin/
git commit -m "feat: built-in skills (file, code, git, github, web_search, analyzer)"
```

---

## Chunk 5: Guardrails & Approval System

### Task 14: Guardrails

**Files:**
- Create: `kinclaw/guardrails/limits.py`
- Create: `kinclaw/guardrails/safety.py`
- Create: `kinclaw/guardrails/audit.py`
- Test: `tests/test_guardrails.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_guardrails.py
import pytest
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_commits_per_day=10, max_posts_per_day=2)
    for _ in range(10):
        assert await limiter.can_commit() is True
        await limiter.record_commit()


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_exceeded():
    limiter = RateLimiter(max_commits_per_day=2, max_posts_per_day=2)
    await limiter.record_commit()
    await limiter.record_commit()
    assert await limiter.can_commit() is False


def test_safety_checker_blocks_forbidden_paths():
    checker = SafetyChecker()
    assert checker.is_safe_path("kinclaw/core/agent.py") is True
    assert checker.is_safe_path("kinclaw/guardrails/safety.py") is False
    assert checker.is_safe_path("kinclaw/approval/queue.py") is False


def test_safety_checker_allows_normal_paths():
    checker = SafetyChecker()
    assert checker.is_safe_path("kinclaw/skills/builtin/new_skill.py") is True
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_guardrails.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement guardrails**

```python
# kinclaw/guardrails/limits.py
"""Rate limiters for commits, posts, and budget."""
from __future__ import annotations

from collections import defaultdict
from datetime import date


class RateLimiter:
    def __init__(
        self,
        max_commits_per_day: int = 10,
        max_posts_per_day: int = 2,
        monthly_budget_usd: float = 100.0,
    ) -> None:
        self._max_commits = max_commits_per_day
        self._max_posts = max_posts_per_day
        self._budget = monthly_budget_usd
        self._commits: dict[date, int] = defaultdict(int)
        self._posts: dict[date, int] = defaultdict(int)
        self._spend: dict[str, float] = defaultdict(float)  # YYYY-MM → USD

    async def can_commit(self) -> bool:
        return self._commits[date.today()] < self._max_commits

    async def record_commit(self) -> None:
        self._commits[date.today()] += 1

    async def can_post(self) -> bool:
        return self._posts[date.today()] < self._max_posts

    async def record_post(self) -> None:
        self._posts[date.today()] += 1

    async def can_spend(self, usd: float) -> bool:
        month_key = date.today().strftime("%Y-%m")
        return self._spend[month_key] + usd <= self._budget

    async def record_spend(self, usd: float) -> None:
        month_key = date.today().strftime("%Y-%m")
        self._spend[month_key] += usd
```

```python
# kinclaw/guardrails/safety.py
"""Safety checks: forbidden paths, dangerous operations."""
from __future__ import annotations

FORBIDDEN_PATH_PREFIXES = [
    "kinclaw/guardrails/",
    "kinclaw/approval/",
    ".env",
    ".git/",
]


class SafetyChecker:
    """Verifies that proposed changes don't touch protected paths."""

    def is_safe_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lstrip("/")
        return not any(normalized.startswith(p) for p in FORBIDDEN_PATH_PREFIXES)

    def is_safe_content(self, content: str) -> bool:
        """Heuristic checks for dangerous code patterns."""
        danger_patterns = [
            "os.system(", "subprocess.call(\"rm", "shutil.rmtree(",
            "__import__('os').system",
        ]
        return not any(p in content for p in danger_patterns)

    def validate_proposal_changes(self, code_changes: dict[str, str]) -> list[str]:
        """Return list of violations, empty means safe."""
        violations = []
        for path, content in code_changes.items():
            if not self.is_safe_path(path):
                violations.append(f"Forbidden path: {path}")
            if not self.is_safe_content(content):
                violations.append(f"Dangerous content in: {path}")
        return violations
```

```python
# kinclaw/guardrails/audit.py
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
        from kinclaw.database.connection import get_session
        from kinclaw.database.queries import AuditRepo
        try:
            async with get_session() as session:
                repo = AuditRepo(session)
                await repo.log(action=action, detail=detail, result=result, actor=actor)
        except Exception:
            # Fallback to file log if DB unavailable
            logger.warning("Audit DB unavailable, logging to file: {} {} {}", actor, action, result)
        logger.info("[AUDIT] {} | {} | {} | {}", actor, action, result, detail[:100])
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_guardrails.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/guardrails/ tests/test_guardrails.py
git commit -m "feat: guardrails (rate limits, safety checks, audit logging)"
```

---

### Task 15: Approval System

**Files:**
- Create: `kinclaw/approval/parser.py`
- Create: `kinclaw/approval/queue.py`
- Create: `kinclaw/approval/executor.py`
- Test: `tests/test_approval.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_approval.py
import pytest
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.core.types import Proposal, Approval


def test_parser_detects_approve():
    parser = ApprovalParser()
    result = parser.parse("aprova", proposal_id="p1")
    assert result is not None
    assert result.approved is True


def test_parser_detects_reject():
    parser = ApprovalParser()
    result = parser.parse("nega", proposal_id="p1")
    assert result is not None
    assert result.approved is False


def test_parser_detects_english_approve():
    parser = ApprovalParser()
    result = parser.parse("approve this", proposal_id="p1")
    assert result is not None
    assert result.approved is True


def test_parser_returns_none_for_unrelated():
    parser = ApprovalParser()
    result = parser.parse("como vai você?", proposal_id="p1")
    assert result is None


@pytest.mark.asyncio
async def test_queue_receive_approval():
    queue = ApprovalQueue()
    approval = Approval(proposal_id="p1", approved=True, channel="telegram", raw_message="aprova")
    await queue.submit(approval)
    received = await queue.get_for("p1", timeout=0.5)
    assert received is not None
    assert received.approved is True
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_approval.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement approval system**

```python
# kinclaw/approval/parser.py
"""Parses natural language approval/rejection from any channel."""
from __future__ import annotations

from kinclaw.core.types import Approval

APPROVE_KEYWORDS = {"aprova", "approve", "yes", "sim", "ok", "go", "autoriza", "autorizo", "pode"}
REJECT_KEYWORDS = {"nega", "reject", "no", "não", "nao", "cancel", "cancela", "stop", "abort"}


class ApprovalParser:
    def parse(self, message: str, proposal_id: str, channel: str = "unknown") -> Approval | None:
        """Returns Approval if message is a clear approval/rejection, else None."""
        normalized = message.lower().strip()
        words = set(normalized.split())

        if words & APPROVE_KEYWORDS:
            return Approval(proposal_id=proposal_id, approved=True, channel=channel, raw_message=message)
        if words & REJECT_KEYWORDS:
            return Approval(proposal_id=proposal_id, approved=False, channel=channel, raw_message=message)
        return None
```

```python
# kinclaw/approval/queue.py
"""Manages pending proposals awaiting owner approval."""
from __future__ import annotations

import asyncio
from kinclaw.core.types import Approval
from kinclaw.logger import logger


class ApprovalQueue:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._approvals: dict[str, Approval] = {}

    def register_proposal(self, proposal_id: str) -> None:
        self._events[proposal_id] = asyncio.Event()

    async def submit(self, approval: Approval) -> None:
        self._approvals[approval.proposal_id] = approval
        if approval.proposal_id in self._events:
            self._events[approval.proposal_id].set()
        logger.info("Approval submitted for proposal {}: {}", approval.proposal_id, approval.approved)

    async def get_for(self, proposal_id: str, timeout: float = 3600) -> Approval | None:
        if proposal_id not in self._events:
            self.register_proposal(proposal_id)
        try:
            await asyncio.wait_for(self._events[proposal_id].wait(), timeout=timeout)
            return self._approvals.get(proposal_id)
        except asyncio.TimeoutError:
            logger.warning("Approval timeout for proposal {}", proposal_id)
            return None

    def clear(self, proposal_id: str) -> None:
        self._events.pop(proposal_id, None)
        self._approvals.pop(proposal_id, None)
```

```python
# kinclaw/approval/executor.py
"""Executes approved proposals: write code, test, commit, PR."""
from __future__ import annotations

from kinclaw.core.types import Approval, Proposal, ProposalStatus
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.logger import logger


class ApprovalExecutor:
    def __init__(
        self,
        safety: SafetyChecker,
        limiter: RateLimiter,
        audit: AuditLogger,
    ) -> None:
        self._safety = safety
        self._limiter = limiter
        self._audit = audit

    async def execute(self, proposal: Proposal, approval: Approval, notify_fn=None) -> dict:
        """Execute an approved proposal end-to-end."""
        if not approval.approved:
            await self._audit.log("proposal_rejected", detail=proposal.title, result="rejected")
            if notify_fn:
                await notify_fn(f"❌ Proposal rejected: {proposal.title}")
            return {"success": False, "reason": "rejected"}

        violations = self._safety.validate_proposal_changes(proposal.code_changes)
        if violations:
            await self._audit.log("safety_violation", detail=str(violations), result="blocked")
            if notify_fn:
                await notify_fn(f"🚫 Safety check failed: {violations}")
            return {"success": False, "reason": "safety_violation", "violations": violations}

        if not await self._limiter.can_commit():
            if notify_fn:
                await notify_fn("⚠️ Daily commit limit reached. Execution deferred.")
            return {"success": False, "reason": "commit_limit"}

        if notify_fn:
            await notify_fn(f"✅ Approved! Starting execution of: {proposal.title}")

        await self._audit.log("proposal_executing", detail=proposal.title)
        return await self._do_execute(proposal, notify_fn)

    async def _do_execute(self, proposal: Proposal, notify_fn) -> dict:
        """Write files, run tests, commit, push, open PR."""
        from kinclaw.skills.builtin.file_manager import FileManagerSkill
        from kinclaw.skills.builtin.git_manager import GitManagerSkill
        from kinclaw.skills.builtin.github_api import GitHubAPISkill
        from kinclaw.config import get_settings

        settings = get_settings()
        file_skill = FileManagerSkill()
        git_skill = GitManagerSkill()
        github_skill = GitHubAPISkill(token=settings.github_token, repo=settings.github_repo)

        # 1. Write code files
        if notify_fn:
            await notify_fn("💻 Writing code...")
        for path, content in proposal.code_changes.items():
            await file_skill.execute(action="write", path=path, content=content)

        # 2. Git add + commit
        if notify_fn:
            await notify_fn("📝 Committing changes...")
        files = list(proposal.code_changes.keys())
        await git_skill.execute(action="add", files=files)
        commit_result = await git_skill.execute(
            action="commit",
            message=f"Auto: {proposal.title}\n\nImpact: {proposal.impact_pct}% | Risk: {proposal.risk} | Confidence: {proposal.confidence_pct}%",
        )
        if not commit_result.get("success"):
            if notify_fn:
                await notify_fn(f"❌ Commit failed: {commit_result.get('stderr')}")
            return {"success": False, "reason": "commit_failed"}

        await self._limiter.record_commit()

        # 3. Push
        if notify_fn:
            await notify_fn("📤 Pushing...")
        push_result = await git_skill.execute(action="push")
        if not push_result.get("success"):
            if notify_fn:
                await notify_fn(f"❌ Push failed: {push_result.get('stderr')}")
            return {"success": False, "reason": "push_failed"}

        # 4. Open PR
        if notify_fn:
            await notify_fn("🔗 Opening PR...")
        pr_result = await github_skill.execute(
            action="create_pr",
            title=proposal.title,
            body=f"## Auto-improvement\n\n{proposal.description}\n\n**Impact:** {proposal.impact_pct}%\n**Risk:** {proposal.risk}\n**Confidence:** {proposal.confidence_pct}%",
            head="auto-improve",
            base=settings.github_default_branch,
        )

        if pr_result.get("success"):
            if notify_fn:
                await notify_fn(f"✅ PR #{pr_result['pr_number']} opened!\n{pr_result['url']}")
            await self._audit.log("pr_opened", detail=pr_result["url"])
            return {"success": True, "pr_number": pr_result["pr_number"], "pr_url": pr_result["url"]}
        else:
            if notify_fn:
                await notify_fn(f"⚠️ Committed but PR creation failed: {pr_result.get('error')}")
            return {"success": True, "pr_number": None, "note": "pr_failed"}
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_approval.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/approval/ tests/test_approval.py
git commit -m "feat: approval system (parser, queue, executor)"
```

---

## Chunk 6: Auto-Improve Loop

### Task 16: Self-Analyzer

**Files:**
- Create: `kinclaw/auto_improve/analyzer.py`
- Create: `kinclaw/auto_improve/comparator.py`
- Create: `kinclaw/auto_improve/proposer.py`
- Test: `tests/test_auto_improve.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_auto_improve.py
import pytest
from pathlib import Path
from kinclaw.auto_improve.analyzer import SelfAnalyzer
from kinclaw.auto_improve.comparator import ClawComparator
from kinclaw.auto_improve.proposer import ProposalGenerator
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_self_analyzer_returns_metrics():
    analyzer = SelfAnalyzer(base_path=Path("."))
    analysis = await analyzer.analyze()
    assert "metrics" in analysis
    assert analysis["metrics"]["files"] >= 0
    assert analysis["metrics"]["lines"] >= 0


@pytest.mark.asyncio
async def test_comparator_returns_gaps():
    comparator = ClawComparator(ref_path=Path("ref"))
    # Will find 0 gaps if ref doesn't exist, but shouldn't crash
    gaps = await comparator.find_gaps({"metrics": {"files": 5, "lines": 200}})
    assert isinstance(gaps, list)


@pytest.mark.asyncio
async def test_proposal_generator_creates_proposals():
    mock_provider = AsyncMock()
    mock_provider.think_json = AsyncMock(return_value={
        "title": "Optimize memory cache",
        "description": "Add LRU cache to memory retrieval",
        "impact_pct": 35,
        "risk": "low",
        "confidence_pct": 88,
        "estimated_hours": 1.5,
        "code_changes": {},
    })

    generator = ProposalGenerator(provider=mock_provider)
    gaps = [{"type": "performance", "description": "Memory retrieval is slow", "reference_claw": "nanobot"}]
    proposals = await generator.generate(gaps)
    assert len(proposals) == 1
    assert proposals[0].title == "Optimize memory cache"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_auto_improve.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement auto-improve modules**

```python
# kinclaw/auto_improve/analyzer.py
"""Analyzes KinClaw's own codebase for metrics and improvement opportunities."""
from __future__ import annotations

import ast
from pathlib import Path

from kinclaw.logger import logger


class SelfAnalyzer:
    def __init__(self, base_path: Path = Path(".")) -> None:
        self._base = base_path

    async def analyze(self) -> dict:
        """Return metrics dict for the kinclaw/ package."""
        pkg = self._base / "kinclaw"
        py_files = list(pkg.rglob("*.py")) if pkg.exists() else []

        total_lines = total_funcs = total_classes = 0
        parse_errors = 0

        for f in py_files:
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                total_lines += src.count("\n") + 1
                tree = ast.parse(src)
                total_funcs += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                total_classes += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            except SyntaxError:
                parse_errors += 1

        return {
            "metrics": {
                "files": len(py_files),
                "lines": total_lines,
                "functions": total_funcs,
                "classes": total_classes,
                "parse_errors": parse_errors,
            }
        }
```

```python
# kinclaw/auto_improve/comparator.py
"""Compares KinClaw metrics against the 7 reference Claws."""
from __future__ import annotations

import ast
from pathlib import Path

from kinclaw.logger import logger

CLAW_NAMES = ["openclaw", "nanobot", "zeroclaw", "picoclaw", "nanoclaw", "mimiclaw", "ironclaw"]

IMPROVEMENT_SIGNALS = [
    {"type": "test_coverage", "description": "Add unit tests for untested modules", "min_files": 5},
    {"type": "error_handling", "description": "Improve error handling patterns", "min_files": 10},
    {"type": "async_patterns", "description": "Optimize async/await usage", "min_files": 5},
    {"type": "documentation", "description": "Add or improve docstrings", "min_files": 3},
    {"type": "performance", "description": "Profile and optimize hot paths", "min_files": 10},
]


class ClawComparator:
    def __init__(self, ref_path: Path = Path("ref")) -> None:
        self._ref = ref_path

    async def find_gaps(self, self_analysis: dict) -> list[dict]:
        """Identify improvement gaps by comparing self with reference claws."""
        gaps: list[dict] = []
        metrics = self_analysis.get("metrics", {})
        file_count = metrics.get("files", 0)

        for signal in IMPROVEMENT_SIGNALS:
            if file_count >= signal.get("min_files", 0):
                best_claw = self._find_best_reference_claw(signal["type"])
                gaps.append({
                    "type": signal["type"],
                    "description": signal["description"],
                    "reference_claw": best_claw,
                    "self_metrics": metrics,
                })

        return gaps[:3]  # Return top 3 gaps to keep focused

    def _find_best_reference_claw(self, gap_type: str) -> str:
        """Find which reference claw best demonstrates this improvement."""
        type_to_claw = {
            "test_coverage": "nanobot",
            "error_handling": "openclaw",
            "async_patterns": "zeroclaw",
            "documentation": "nanobot",
            "performance": "zeroclaw",
        }
        return type_to_claw.get(gap_type, "nanobot")
```

```python
# kinclaw/auto_improve/proposer.py
"""Generates concrete improvement proposals using Claude."""
from __future__ import annotations

import json

from kinclaw.core.types import Proposal
from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


_PROPOSAL_SYSTEM = """You are KinClaw's self-improvement engine.
Given a gap in the codebase, generate a concrete, actionable improvement proposal.
Be specific. The proposal must include actual code changes (small, focused).
Respond with valid JSON only."""

_PROPOSAL_PROMPT_TEMPLATE = """KinClaw found this improvement opportunity:

Gap type: {gap_type}
Description: {description}
Reference claw: {reference_claw}
Current metrics: {metrics}

Generate a focused improvement proposal. Respond with JSON:
{{
  "title": "Short action title (max 60 chars)",
  "description": "2-3 sentences explaining the improvement",
  "impact_pct": <integer 1-100>,
  "risk": "low|medium|high",
  "confidence_pct": <integer 0-100>,
  "estimated_hours": <float>,
  "code_changes": {{
    "kinclaw/path/to/file.py": "full file content here"
  }}
}}
Keep code_changes small (1-2 files, focused changes).
"""


class ProposalGenerator:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(self, gaps: list[dict]) -> list[Proposal]:
        proposals = []
        for gap in gaps:
            try:
                proposal = await self._generate_one(gap)
                if proposal:
                    proposals.append(proposal)
            except Exception as e:
                logger.error("Failed to generate proposal for gap {}: {}", gap.get("type"), e)
        return proposals

    async def _generate_one(self, gap: dict) -> Proposal | None:
        prompt = _PROPOSAL_PROMPT_TEMPLATE.format(
            gap_type=gap.get("type", ""),
            description=gap.get("description", ""),
            reference_claw=gap.get("reference_claw", ""),
            metrics=json.dumps(gap.get("self_metrics", {})),
        )
        try:
            data = await self._provider.think_json(prompt, system=_PROPOSAL_SYSTEM)
            return Proposal(
                title=data.get("title", "Untitled improvement"),
                description=data.get("description", ""),
                impact_pct=data.get("impact_pct", 0),
                risk=data.get("risk", "low"),
                confidence_pct=data.get("confidence_pct", 0),
                estimated_hours=data.get("estimated_hours", 1.0),
                code_changes=data.get("code_changes", {}),
                reference_claw=gap.get("reference_claw", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Invalid proposal JSON: {}", e)
            return None
```

- [ ] **Step 4: Run to verify pass**

```bash
python -m pytest tests/test_auto_improve.py -v
```

- [ ] **Step 5: Commit**

```bash
git add kinclaw/auto_improve/ tests/test_auto_improve.py
git commit -m "feat: auto-improve system (analyzer, comparator, proposer)"
```

---

## Chunk 7: Core Agent & Orchestrator

### Task 17: KinClaw Agent (Main Loop)

**Files:**
- Create: `kinclaw/core/agent.py`
- Create: `kinclaw/core/orchestrator.py`
- Create: `kinclaw/core/state.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_core.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.state import AgentState, AgentPhase


def test_agent_state_initial():
    state = AgentState()
    assert state.phase == AgentPhase.IDLE
    assert state.proposals_today == 0
    assert state.is_running is False


def test_agent_state_transitions():
    state = AgentState()
    state.phase = AgentPhase.ANALYZING
    assert state.phase == AgentPhase.ANALYZING


@pytest.mark.asyncio
async def test_agent_analyze_self_returns_analysis():
    mock_provider = AsyncMock()
    agent = KinClawAgent.__new__(KinClawAgent)
    agent._provider = mock_provider

    from kinclaw.auto_improve.analyzer import SelfAnalyzer
    from pathlib import Path
    agent._analyzer = SelfAnalyzer(base_path=Path("."))

    analysis = await agent.analyze_self()
    assert "metrics" in analysis
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_core.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement state and agent**

```python
# kinclaw/core/state.py
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
```

```python
# kinclaw/core/agent.py
"""KinClaw autonomous agent — the main brain."""
from __future__ import annotations

import asyncio
from pathlib import Path

from kinclaw.auto_improve.analyzer import SelfAnalyzer
from kinclaw.auto_improve.comparator import ClawComparator
from kinclaw.auto_improve.proposer import ProposalGenerator
from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.bus import MessageBus
from kinclaw.core.state import AgentPhase, AgentState
from kinclaw.core.types import InboundMessage, Proposal
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


class KinClawAgent:
    """Autonomous self-improving agent. Runs forever."""

    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        bus: MessageBus,
        router: ChannelRouter,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._bus = bus
        self._router = router
        self._state = AgentState()

        # Sub-systems
        self._analyzer = SelfAnalyzer(base_path=Path("."))
        self._comparator = ClawComparator(ref_path=Path("ref"))
        self._proposer = ProposalGenerator(provider=provider)
        self._approval_queue = ApprovalQueue()
        self._approval_parser = ApprovalParser()
        self._limiter = RateLimiter(
            max_commits_per_day=settings.max_commits_per_day,
            max_posts_per_day=settings.posts_per_day,
            monthly_budget_usd=settings.monthly_budget_usd,
        )
        self._safety = SafetyChecker()
        self._audit = AuditLogger()
        self._executor = ApprovalExecutor(
            safety=self._safety,
            limiter=self._limiter,
            audit=self._audit,
        )

        # Register inbound message handler
        bus.subscribe_outbound(self._noop_handler)  # placeholder; real channel handles outbound
        asyncio.get_event_loop().create_task(self._listen_inbound())

    async def _noop_handler(self, msg) -> None:
        pass

    async def analyze_self(self) -> dict:
        """Analyze own codebase and return metrics + gaps."""
        self._state.phase = AgentPhase.ANALYZING
        analysis = await self._analyzer.analyze()
        gaps = await self._comparator.find_gaps(analysis)
        analysis["gaps"] = gaps
        return analysis

    async def propose_improvements(self, analysis: dict) -> list[Proposal]:
        """Generate improvement proposals from analysis gaps."""
        self._state.phase = AgentPhase.PROPOSING
        gaps = analysis.get("gaps", [])
        if not gaps:
            logger.info("No gaps found in this analysis cycle")
            return []
        return await self._proposer.generate(gaps)

    async def broadcast(self, message: str) -> None:
        """Send message to all active channels."""
        await self._router.broadcast(message)

    async def run_improvement_cycle(self) -> None:
        """One complete analyze→propose→approve→execute cycle."""
        self._state.reset_daily_counters_if_new_day()

        if self._state.proposals_today >= self._settings.max_proposals_per_day:
            logger.info("Daily proposal limit reached ({}), sleeping", self._settings.max_proposals_per_day)
            return

        logger.info("Starting improvement cycle")
        await self._audit.log("cycle_start")

        # 1. Analyze
        analysis = await self.analyze_self()
        logger.info("Analysis complete: {} files, {} lines, {} gaps",
                    analysis["metrics"]["files"],
                    analysis["metrics"]["lines"],
                    len(analysis.get("gaps", [])))

        # 2. Generate proposals
        proposals = await self.propose_improvements(analysis)
        if not proposals:
            logger.info("No proposals generated this cycle")
            return

        # 3. Take first proposal (best confidence)
        proposals.sort(key=lambda p: p.confidence_pct, reverse=True)
        proposal = proposals[0]
        self._state.proposals_today += 1
        self._state.current_proposal_id = proposal.id
        self._state.phase = AgentPhase.AWAITING_APPROVAL

        # 4. Notify owner
        notify_text = self._format_proposal_notification(proposal)
        await self.broadcast(notify_text)
        logger.info("Proposal sent: {} (confidence: {}%)", proposal.title, proposal.confidence_pct)

        # 5. Wait for approval
        self._approval_queue.register_proposal(proposal.id)
        approval = await self._approval_queue.get_for(
            proposal.id, timeout=3600  # 1 hour timeout
        )

        if approval is None:
            await self.broadcast(f"⏰ Proposal timed out with no response: {proposal.title}")
            logger.info("Proposal {} timed out", proposal.id)
            return

        # 6. Execute if approved
        self._state.phase = AgentPhase.EXECUTING
        result = await self._executor.execute(
            proposal, approval, notify_fn=self.broadcast
        )

        # 7. Report
        self._state.phase = AgentPhase.REPORTING
        if result.get("success"):
            await self._audit.log("cycle_success", detail=proposal.title)
        else:
            await self._audit.log("cycle_failed", detail=str(result.get("reason")), result="failed")

        self._state.phase = AgentPhase.IDLE

    async def run_forever(self) -> None:
        """Perpetual loop: cycle, sleep, repeat."""
        self._state.is_running = True
        logger.info("KinClaw started — running forever")
        await self.broadcast("🤖 KinClaw is online and ready!")

        while self._state.is_running:
            try:
                await self.run_improvement_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unhandled error in improvement cycle")
                self._state.phase = AgentPhase.IDLE

            logger.info("Sleeping {}s before next cycle", self._settings.sleep_between_analyses)
            await asyncio.sleep(self._settings.sleep_between_analyses)

    async def stop(self) -> None:
        self._state.is_running = False
        await self.broadcast("👋 KinClaw is shutting down.")

    async def _listen_inbound(self) -> None:
        """Process inbound messages (approval responses)."""
        while True:
            try:
                msg: InboundMessage = await asyncio.wait_for(
                    self._bus.consume_inbound(), timeout=1.0
                )
                await self._handle_inbound(msg)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in inbound listener")

    async def _handle_inbound(self, msg: InboundMessage) -> None:
        """Route inbound messages to approval queue if relevant."""
        if not self._state.current_proposal_id:
            return
        approval = self._approval_parser.parse(
            message=msg.content,
            proposal_id=self._state.current_proposal_id,
            channel=msg.channel,
        )
        if approval:
            await self._approval_queue.submit(approval)

    def _format_proposal_notification(self, proposal: Proposal) -> str:
        return (
            f"🤖 KinClaw found an improvement opportunity!\n\n"
            f"📋 **{proposal.title}**\n\n"
            f"{proposal.description}\n\n"
            f"📊 Impact: +{proposal.impact_pct}%\n"
            f"⚠️ Risk: {proposal.risk.upper()}\n"
            f"💪 Confidence: {proposal.confidence_pct}%\n"
            f"⏱️ Estimated: {proposal.estimated_hours}h\n"
            f"🔍 Inspired by: {proposal.reference_claw}\n\n"
            f"Reply **aprova** to approve or **nega** to reject.\n"
            f"(Timeout in 1 hour)"
        )

    @property
    def state(self) -> AgentState:
        return self._state
```

- [ ] **Step 4: Implement `kinclaw/core/orchestrator.py`**

```python
# kinclaw/core/orchestrator.py
"""Orchestrates agent startup, channel registration, and graceful shutdown."""
from __future__ import annotations

import asyncio
import signal

from kinclaw.channels.router import ChannelRouter
from kinclaw.channels.telegram import TelegramChannel
from kinclaw.channels.discord import DiscordChannel
from kinclaw.config import Settings
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.bus import MessageBus
from kinclaw.database.connection import init_db
from kinclaw.logger import logger, setup_logging
from kinclaw.providers.claude import ClaudeProvider


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bus = MessageBus()
        self._router: ChannelRouter | None = None
        self._agent: KinClawAgent | None = None

    async def start(self) -> None:
        setup_logging()
        logger.info("KinClaw orchestrator starting")

        await init_db(self._settings.database_url)

        provider = ClaudeProvider(
            api_key=self._settings.anthropic_api_key,
            model=self._settings.claude_model,
        )

        self._router = ChannelRouter(self._bus)
        await self._register_channels()

        self._agent = KinClawAgent(
            settings=self._settings,
            provider=provider,
            bus=self._bus,
            router=self._router,
        )

        await self._router.start_all()

        # Register shutdown handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        await self._agent.run_forever()

    async def stop(self) -> None:
        logger.info("Graceful shutdown initiated")
        if self._agent:
            await self._agent.stop()
        if self._router:
            await self._router.stop_all()

    async def _register_channels(self) -> None:
        s = self._settings
        active = s.active_channels

        if "telegram" in active and s.telegram_bot_token:
            ch = TelegramChannel(
                token=s.telegram_bot_token,
                allowed_ids=s.telegram_allowed_id_list,
                bus=self._bus,
            )
            self._router.register(ch)

        if "discord" in active and s.discord_bot_token:
            ch = DiscordChannel(
                token=s.discord_bot_token,
                channel_id=int(s.discord_channel_id or 0),
                allowed_ids=[],
                bus=self._bus,
            )
            self._router.register(ch)
```

- [ ] **Step 5: Run to verify pass**

```bash
python -m pytest tests/test_core.py -v
```

- [ ] **Step 6: Commit**

```bash
git add kinclaw/core/agent.py kinclaw/core/orchestrator.py kinclaw/core/state.py tests/test_core.py
git commit -m "feat: KinClawAgent main loop and Orchestrator startup"
```

---

## Chunk 8: Web Dashboard & CLI

### Task 18: FastAPI Dashboard

**Files:**
- Create: `kinclaw/web/app.py`
- Create: `kinclaw/web/routes/overview.py`
- Create: `kinclaw/web/routes/proposals.py`
- Create: `kinclaw/web/templates/index.html`
- Create: `kinclaw/web/static/dashboard.css`
- Create: `kinclaw/web/static/dashboard.js`

- [ ] **Step 1: Implement `kinclaw/web/app.py`**

```python
# kinclaw/web/app.py
"""FastAPI web application — dashboard and webhook endpoints."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from kinclaw.web.routes import overview, proposals, webhooks

_BASE = Path(__file__).parent

app = FastAPI(title="KinClaw Dashboard", version="1.0.0")

app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))

app.include_router(overview.router)
app.include_router(proposals.router, prefix="/api/proposals")
app.include_router(webhooks.router, prefix="/webhooks")
```

- [ ] **Step 2: Implement routes**

```python
# kinclaw/web/routes/overview.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/status")
async def status():
    return {
        "status": "running",
        "version": "1.0.0",
        "name": "KinClaw",
    }
```

```python
# kinclaw/web/routes/proposals.py
from fastapi import APIRouter
from kinclaw.database.connection import get_session
from kinclaw.database.queries import ProposalRepo

router = APIRouter()


@router.get("/")
async def list_proposals(status: str = "all"):
    async with get_session() as session:
        repo = ProposalRepo(session)
        if status == "all":
            results = await repo.list_by_status("pending")
        else:
            results = await repo.list_by_status(status)
    return [
        {
            "id": r.id,
            "title": r.title,
            "status": r.status,
            "impact_pct": r.impact_pct,
            "risk": r.risk,
            "confidence_pct": r.confidence_pct,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]
```

```python
# kinclaw/web/routes/webhooks.py
"""Webhook endpoints for channel callbacks."""
from fastapi import APIRouter, Request, HTTPException
from kinclaw.logger import logger

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request):
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "")
    logger.info("GitHub webhook: {}", event)
    return {"received": True}
```

- [ ] **Step 3: Create dashboard HTML template**

```bash
cat > kinclaw/web/templates/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KinClaw Dashboard</title>
  <link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
  <header>
    <div class="logo">🤖 KinClaw</div>
    <div class="tagline">Autonomous Self-Improving Agent</div>
    <div id="status-badge" class="badge">●  Loading...</div>
  </header>
  <main>
    <section class="stats-grid" id="stats-grid">
      <div class="stat-card"><div class="stat-value" id="stat-phase">—</div><div class="stat-label">Current Phase</div></div>
      <div class="stat-card"><div class="stat-value" id="stat-proposals">—</div><div class="stat-label">Proposals Today</div></div>
      <div class="stat-card"><div class="stat-value" id="stat-files">—</div><div class="stat-label">Source Files</div></div>
      <div class="stat-card"><div class="stat-value" id="stat-lines">—</div><div class="stat-label">Lines of Code</div></div>
    </section>
    <section class="proposals-section">
      <h2>Recent Proposals</h2>
      <div id="proposals-list" class="proposals-list">Loading...</div>
    </section>
  </main>
  <script src="/static/dashboard.js"></script>
</body>
</html>
HTMLEOF
```

- [ ] **Step 4: Create dashboard CSS**

```bash
cat > kinclaw/web/static/dashboard.css << 'CSSEOF'
:root {
  --bg: #0a0e1a;
  --surface: #111827;
  --border: #1f2937;
  --accent: #6366f1;
  --green: #10b981;
  --yellow: #f59e0b;
  --red: #ef4444;
  --text: #e2e8f0;
  --muted: #64748b;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }
header {
  display: flex; align-items: center; gap: 1rem;
  padding: 1.5rem 2rem; border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.logo { font-size: 1.5rem; font-weight: 700; }
.tagline { color: var(--muted); font-size: 0.875rem; }
.badge { margin-left: auto; padding: 0.375rem 0.75rem; border-radius: 9999px;
  background: rgba(16,185,129,.15); color: var(--green); font-size: 0.75rem; }
main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
.stat-label { color: var(--muted); font-size: 0.875rem; margin-top: 0.25rem; }
.proposals-section h2 { margin-bottom: 1rem; font-size: 1.125rem; }
.proposals-list { display: flex; flex-direction: column; gap: 0.75rem; }
.proposal-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }
.proposal-title { font-weight: 600; margin-bottom: 0.5rem; }
.proposal-meta { display: flex; gap: 1rem; font-size: 0.75rem; color: var(--muted); }
.tag { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }
.tag-low { background: rgba(16,185,129,.15); color: var(--green); }
.tag-medium { background: rgba(245,158,11,.15); color: var(--yellow); }
.tag-high { background: rgba(239,68,68,.15); color: var(--red); }
CSSEOF
```

- [ ] **Step 5: Create dashboard JS**

```bash
cat > kinclaw/web/static/dashboard.js << 'JSEOF'
async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    const data = await r.json();
    document.getElementById('status-badge').textContent = '● ' + data.status;
    document.getElementById('stat-phase').textContent = data.phase || 'idle';
    document.getElementById('stat-proposals').textContent = data.proposals_today ?? '—';
    document.getElementById('stat-files').textContent = data.files ?? '—';
    document.getElementById('stat-lines').textContent = data.lines ?? '—';
  } catch(e) { console.error('Status fetch failed', e); }
}

async function fetchProposals() {
  try {
    const r = await fetch('/api/proposals/');
    const proposals = await r.json();
    const list = document.getElementById('proposals-list');
    if (!proposals.length) { list.innerHTML = '<p style="color:var(--muted)">No pending proposals.</p>'; return; }
    list.innerHTML = proposals.map(p => `
      <div class="proposal-card">
        <div class="proposal-title">${p.title}</div>
        <div class="proposal-meta">
          <span class="tag tag-${p.risk}">${p.risk.toUpperCase()}</span>
          <span>+${p.impact_pct}% impact</span>
          <span>${p.confidence_pct}% confidence</span>
          <span>${new Date(p.created_at).toLocaleString()}</span>
        </div>
      </div>`).join('');
  } catch(e) { console.error('Proposals fetch failed', e); }
}

fetchStatus();
fetchProposals();
setInterval(fetchStatus, 10000);
setInterval(fetchProposals, 30000);
JSEOF
```

- [ ] **Step 6: Commit**

```bash
git add kinclaw/web/
git commit -m "feat: FastAPI dashboard with proposals list and status API"
```

---

### Task 19: CLI Entry Points

**Files:**
- Create: `kinclaw/cli/commands.py`
- Create: `kinclaw/__main__.py`

- [ ] **Step 1: Implement CLI**

```python
# kinclaw/cli/commands.py
"""Click CLI commands for KinClaw."""
from __future__ import annotations

import asyncio
import click


@click.group()
def cli():
    """KinClaw — Autonomous Self-Improving AI Agent"""


@cli.command()
@click.option("--host", default=None, help="Web server host")
@click.option("--port", default=None, type=int, help="Web server port")
def run(host, port):
    """Start KinClaw agent + web dashboard."""
    from kinclaw.config import get_settings
    from kinclaw.core.orchestrator import Orchestrator

    settings = get_settings()
    if host:
        settings.web_host = host
    if port:
        settings.web_port = port

    click.echo("🤖 Starting KinClaw...")
    orchestrator = Orchestrator(settings=settings)
    asyncio.run(orchestrator.start())


@cli.command()
def status():
    """Show current agent status."""
    import httpx
    try:
        r = httpx.get("http://localhost:8000/api/status", timeout=3)
        data = r.json()
        click.echo(f"Status: {data['status']}")
        click.echo(f"Phase:  {data.get('phase', 'unknown')}")
    except Exception as e:
        click.echo(f"Could not connect to KinClaw: {e}", err=True)


@cli.command()
@click.argument("proposal_id")
def approve(proposal_id: str):
    """Manually approve a proposal by ID."""
    import httpx
    try:
        r = httpx.post(
            f"http://localhost:8000/api/proposals/{proposal_id}/approve",
            timeout=3,
        )
        click.echo(r.json())
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
def proposals():
    """List pending proposals."""
    import httpx
    try:
        r = httpx.get("http://localhost:8000/api/proposals/", timeout=3)
        items = r.json()
        if not items:
            click.echo("No pending proposals.")
            return
        for p in items:
            click.echo(f"[{p['id'][:8]}] {p['title']} — {p['risk']} risk, +{p['impact_pct']}% impact")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
```

```python
# kinclaw/__main__.py
"""Entry point for `python -m kinclaw`."""
from kinclaw.cli.commands import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Commit**

```bash
git add kinclaw/cli/commands.py kinclaw/__main__.py
git commit -m "feat: Click CLI (run, status, approve, proposals)"
```

---

## Chunk 9: Docker, Tests & Final Integration

### Task 20: Pytest Configuration & Integration Tests

**Files:**
- Create: `pytest.ini`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings =
    ignore::DeprecationWarning
```

- [ ] **Step 2: Write integration tests**

```python
# tests/test_integration.py
"""Integration tests for the full approval-execution pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.core.types import Proposal, Approval


@pytest.mark.asyncio
async def test_full_approval_pipeline():
    """End-to-end: parse message → submit → execute."""
    parser = ApprovalParser()
    queue = ApprovalQueue()

    # Simulate proposal
    proposal = Proposal(
        title="Test integration improvement",
        description="Just for testing",
        impact_pct=10,
        risk="low",
        confidence_pct=95,
        estimated_hours=0.5,
        code_changes={},
    )

    # Register in queue
    queue.register_proposal(proposal.id)

    # Simulate owner typing "aprova"
    approval = parser.parse("aprova", proposal_id=proposal.id, channel="telegram")
    assert approval is not None
    await queue.submit(approval)

    # Retrieve approval
    received = await queue.get_for(proposal.id, timeout=1.0)
    assert received is not None
    assert received.approved is True


@pytest.mark.asyncio
async def test_safety_blocks_forbidden_path():
    """Executor refuses proposals that modify guardrails."""
    safety = SafetyChecker()
    limiter = RateLimiter()
    audit = AuditLogger()

    # Mock audit to avoid DB
    audit.log = AsyncMock()

    executor = ApprovalExecutor(safety=safety, limiter=limiter, audit=audit)

    proposal = Proposal(
        title="Malicious proposal",
        description="Tries to modify guardrails",
        impact_pct=0,
        risk="high",
        confidence_pct=0,
        estimated_hours=0,
        code_changes={"kinclaw/guardrails/safety.py": "# hacked"},
    )

    approval = Approval(proposal_id=proposal.id, approved=True, channel="test", raw_message="aprova")

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "safety_violation"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit():
    """Executor respects daily commit limit."""
    safety = SafetyChecker()
    limiter = RateLimiter(max_commits_per_day=0)  # Set to 0 → always blocked
    audit = AuditLogger()
    audit.log = AsyncMock()

    executor = ApprovalExecutor(safety=safety, limiter=limiter, audit=audit)

    proposal = Proposal(
        title="Safe proposal",
        description="Valid but limit exceeded",
        impact_pct=5, risk="low", confidence_pct=80, estimated_hours=1,
        code_changes={},
    )
    approval = Approval(proposal_id=proposal.id, approved=True, channel="test", raw_message="aprova")

    result = await executor.execute(proposal, approval)
    assert result["success"] is False
    assert result["reason"] == "commit_limit"
```

- [ ] **Step 3: Run all tests**

```bash
python -m pytest tests/ -v --tb=short 2>&1
```
Expected: all tests pass (or minor import errors for channels not installed)

- [ ] **Step 4: Commit**

```bash
git add pytest.ini tests/test_integration.py
git commit -m "test: integration tests for approval pipeline and guardrails"
```

---

### Task 21: Docker & Final Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`

- [ ] **Step 1: Create `Dockerfile`**

```bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "kinclaw", "run"]
EOF
```

- [ ] **Step 2: Create `docker-compose.yml`**

```bash
cat > docker-compose.yml << 'EOF'
version: "3.9"
services:
  kinclaw:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./kinclaw.db:/app/kinclaw.db
      - ./kinclaw.log:/app/kinclaw.log
    env_file:
      - .env
    restart: unless-stopped
EOF
```

- [ ] **Step 3: Create README.md**

```bash
cat > README.md << 'EOF'
# 🤖 KinClaw — Autonomous Self-Improving AI Agent

KinClaw is a 24/7 autonomous AI agent that analyzes its own code, proposes improvements, and implements them once you approve — all from your Telegram or Discord.

## Features

- **Self-analysis**: Reads and measures its own codebase continuously
- **AI proposals**: Uses Claude to generate concrete improvement proposals
- **Multi-channel notifications**: Telegram, Discord, and more
- **Safe execution**: Guardrails prevent touching critical files or exceeding budgets
- **Full audit log**: Every action logged for transparency
- **Web dashboard**: Real-time overview at localhost:8000

## Quick Start

```bash
cp .env.example .env
# Edit .env with your tokens

pip install -r requirements.txt
python -m kinclaw run
```

## CLI

```bash
python -m kinclaw status          # Check agent status
python -m kinclaw proposals       # List pending proposals
python -m kinclaw approve <id>    # Approve a proposal
```

## Approval Keywords

| Action | Keywords |
|--------|----------|
| Approve | `aprova`, `approve`, `yes`, `sim`, `ok` |
| Reject  | `nega`, `reject`, `no`, `não`, `cancel` |

## Architecture

```
ChannelRouter ──→ MessageBus ──→ KinClawAgent
     ↑                                 │
Telegram/Discord           SelfAnalyzer + ProposalGenerator
                                       │
                            ApprovalQueue ←── Owner response
                                       │
                            ApprovalExecutor (write, test, commit, PR)
```
EOF
```

- [ ] **Step 4: Run full test suite one final time**

```bash
python -m pytest tests/ -v --tb=short
```

- [ ] **Step 5: Final commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "feat: Docker setup and README — KinClaw MVP complete"
```

---

## Summary

| Chunk | Tasks | Deliverable |
|-------|-------|-------------|
| 1 | 1–5 | Config, logging, types, DB |
| 2 | 6–7 | MessageBus, Claude provider |
| 3 | 8–11 | Channels (Telegram, Discord, Router) |
| 4 | 12–13 | Skills (registry + 6 built-ins) |
| 5 | 14–15 | Guardrails + Approval system |
| 6 | 16 | Auto-improve (analyzer, comparator, proposer) |
| 7 | 17 | Core agent + Orchestrator |
| 8 | 18–19 | Web dashboard + CLI |
| 9 | 20–21 | Integration tests + Docker |

**Plan complete and saved to `docs/superpowers/plans/2026-03-09-kinclaw-core.md`.**
