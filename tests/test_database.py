import sqlite3

import pytest
from sqlalchemy import text
from kinclaw.database.connection import init_db, get_session
from kinclaw.database.queries import ApprovalRepo, ProposalRepo
from kinclaw.core.types import Approval, Proposal


@pytest.fixture(autouse=True)
async def db():
    await init_db("sqlite+aiosqlite:///:memory:")
    yield


@pytest.mark.asyncio
async def test_create_and_fetch_proposal():
    async with get_session() as session:
        repo = ProposalRepo(session)
        rec = await repo.create(
            id="p1",
            title="Test",
            description="desc",
            impact_pct=10,
            risk="low",
            confidence_pct=80,
        )
        assert rec.id == "p1"
        fetched = await repo.get("p1")
        assert fetched is not None
        assert fetched.title == "Test"


@pytest.mark.asyncio
async def test_list_pending():
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(
            id="p2",
            title="A",
            description="d",
            impact_pct=5,
            risk="low",
            confidence_pct=60,
        )
        results = await repo.list_by_status("pending")
        assert len(results) >= 1


@pytest.mark.asyncio
async def test_save_proposal_and_update_status():
    async with get_session() as session:
        repo = ProposalRepo(session)
        proposal = Proposal(
            id="p3",
            title="Saved",
            description="saved proposal",
            impact_pct=12,
            risk="medium",
            confidence_pct=88,
            estimated_hours=3.0,
            reference_claw="claw",
        )

        rec = await repo.save_proposal(proposal)
        await repo.update_status("p3", "executing")

        assert rec.id == "p3"
        fetched = await repo.get("p3")
        assert fetched is not None
        assert fetched.status == "executing"
        assert fetched.reference_claw == "claw"


@pytest.mark.asyncio
async def test_save_and_fetch_approval_decision():
    async with get_session() as session:
        repo = ApprovalRepo(session)
        approval = Approval(
            proposal_id="p4",
            approved=False,
            channel="discord",
            raw_message="nega p4",
        )

        rec = await repo.save_decision(approval)
        fetched = await repo.get_by_proposal_id("p4")

        assert rec.proposal_id == "p4"
        assert fetched is not None
        assert fetched.decision == "rejected"
        assert fetched.channel == "discord"


@pytest.mark.asyncio
async def test_init_db_migrates_existing_pre_task3_sqlite_schema(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE proposals (
            id TEXT PRIMARY KEY,
            title VARCHAR(256),
            description TEXT,
            impact_pct INTEGER,
            risk VARCHAR(16),
            confidence_pct INTEGER,
            estimated_hours FLOAT,
            status VARCHAR(32),
            reference_claw VARCHAR(64),
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action VARCHAR(128),
            actor VARCHAR(64),
            detail TEXT,
            result VARCHAR(16),
            created_at DATETIME
        )
        """
    )
    conn.commit()
    conn.close()

    await init_db(f"sqlite+aiosqlite:///{db_path}")

    async with get_session() as session:
        column_rows = await session.execute(text("PRAGMA table_info(proposals)"))
        table_rows = await session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='approval_decisions'"
            )
        )

    column_names = {row[1] for row in column_rows}
    table_names = {row[0] for row in table_rows}

    assert "code_changes" in column_names
    assert "test_changes" in column_names
    assert "approval_decisions" in table_names
