"""Async SQLAlchemy engine factory and session context manager."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
