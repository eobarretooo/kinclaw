import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from kinclaw.auto_improve.analyzer import SelfAnalyzer
from kinclaw.auto_improve.comparator import ClawComparator
from kinclaw.auto_improve.proposer import ProposalGenerator


@pytest.mark.asyncio
async def test_self_analyzer_returns_metrics():
    analyzer = SelfAnalyzer(base_path=Path("."))
    analysis = await analyzer.analyze()
    assert "metrics" in analysis
    assert analysis["metrics"]["files"] >= 0
    assert analysis["metrics"]["lines"] >= 0


@pytest.mark.asyncio
async def test_self_analyzer_counts_kinclaw_files():
    analyzer = SelfAnalyzer(base_path=Path("."))
    analysis = await analyzer.analyze()
    # kinclaw package has many files at this point
    assert analysis["metrics"]["files"] > 10
    assert analysis["metrics"]["functions"] > 20


@pytest.mark.asyncio
async def test_comparator_returns_gaps():
    comparator = ClawComparator(ref_path=Path("ref"))
    gaps = await comparator.find_gaps({"metrics": {"files": 20, "lines": 500}})
    assert isinstance(gaps, list)
    assert len(gaps) > 0  # has enough files to trigger signals
    assert all("type" in g for g in gaps)
    assert all("description" in g for g in gaps)
    assert all("reference_claw" in g for g in gaps)


@pytest.mark.asyncio
async def test_comparator_returns_no_gaps_for_tiny_codebase():
    comparator = ClawComparator(ref_path=Path("ref"))
    gaps = await comparator.find_gaps({"metrics": {"files": 1, "lines": 10}})
    assert isinstance(gaps, list)
    assert len(gaps) == 0  # no signal fires for 1 file


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
    gaps = [{"type": "performance", "description": "Memory retrieval is slow", "reference_claw": "nanobot", "self_metrics": {}}]
    proposals = await generator.generate(gaps)
    assert len(proposals) == 1
    assert proposals[0].title == "Optimize memory cache"
    assert proposals[0].confidence_pct == 88


@pytest.mark.asyncio
async def test_proposal_generator_handles_bad_json():
    mock_provider = AsyncMock()
    mock_provider.think_json = AsyncMock(side_effect=ValueError("bad json"))

    generator = ProposalGenerator(provider=mock_provider)
    gaps = [{"type": "test_coverage", "description": "Missing tests", "reference_claw": "nanobot", "self_metrics": {}}]
    proposals = await generator.generate(gaps)
    assert len(proposals) == 0  # gracefully returns empty list
