import pytest
from kinclaw.database.connection import init_db, get_session
from kinclaw.database.queries import ProposalRepo
from kinclaw.core.types import Proposal


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
