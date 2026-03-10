import pytest
from kinclaw.database.connection import init_db, get_session
from kinclaw.database.queries import ProposalRepo


@pytest.fixture(autouse=True)
async def db():
    await init_db("sqlite+aiosqlite:///:memory:")
    yield


@pytest.mark.asyncio
async def test_create_and_fetch_proposal():
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
async def test_list_pending():
    async with get_session() as session:
        repo = ProposalRepo(session)
        await repo.create(id="p2", title="A", description="d", impact_pct=5, risk="low", confidence_pct=60)
        results = await repo.list_by_status("pending")
        assert len(results) >= 1
