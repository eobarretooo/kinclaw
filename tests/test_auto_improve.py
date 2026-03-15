import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from kinclaw.auto_improve.analyzer import SelfAnalyzer
from kinclaw.auto_improve.comparator import ClawComparator
from kinclaw.auto_improve.proposer import ProposalGenerator


@pytest.mark.asyncio
async def test_self_analyzer_returns_richer_metrics(tmp_path):
    pkg = tmp_path / "kinclaw"
    pkg.mkdir()
    (pkg / "service.py").write_text(
        '"""Service module."""\n\n'
        "async def fetch_data():\n"
        '    """Fetch data asynchronously."""\n'
        "    return 1\n\n"
        "def helper():\n"
        "    return 2\n\n"
        "class Worker:\n"
        '    """Background worker."""\n'
        "    pass\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_service.py").write_text(
        "def test_fetch_data():\n    assert True\n",
        encoding="utf-8",
    )

    analyzer = SelfAnalyzer(base_path=tmp_path)
    analysis = await analyzer.analyze()

    assert "metrics" in analysis
    metrics = analysis["metrics"]
    assert metrics["files"] == 1
    assert metrics["functions"] == 2
    assert metrics["async_functions"] == 1
    assert metrics["classes"] == 1
    assert metrics["test_files"] == 1
    assert metrics["non_test_files"] == 1
    assert metrics["docstring_coverage_pct"] > 0
    assert metrics["largest_files"][0]["path"] == "kinclaw/service.py"


@pytest.mark.asyncio
async def test_self_analyzer_tracks_parse_errors(tmp_path):
    pkg = tmp_path / "kinclaw"
    pkg.mkdir()
    (pkg / "broken.py").write_text("def nope(:\n", encoding="utf-8")

    analyzer = SelfAnalyzer(base_path=tmp_path)
    analysis = await analyzer.analyze()

    assert analysis["metrics"]["parse_errors"] == 1


@pytest.mark.asyncio
async def test_comparator_uses_real_reference_metrics(tmp_path):
    ref_root = tmp_path / "ref"
    nanobot = ref_root / "nanobot" / "kinclaw"
    nanobot.mkdir(parents=True)
    (nanobot / "doc_module.py").write_text(
        '"""Reference docs."""\n\n'
        "def documented():\n"
        '    """Documented."""\n'
        "    return 1\n",
        encoding="utf-8",
    )
    ref_tests = ref_root / "nanobot" / "tests"
    ref_tests.mkdir(parents=True)
    (ref_tests / "test_doc_module.py").write_text(
        "def test_documented():\n    assert True\n",
        encoding="utf-8",
    )

    comparator = ClawComparator(ref_path=ref_root)
    gaps = await comparator.find_gaps(
        {
            "metrics": {
                "files": 1,
                "lines": 5,
                "functions": 1,
                "classes": 0,
                "parse_errors": 0,
                "docstring_coverage_pct": 0.0,
                "async_functions": 0,
                "test_files": 0,
                "non_test_files": 1,
                "largest_files": [],
            }
        }
    )

    assert isinstance(gaps, list)
    assert len(gaps) > 0
    assert any(gap["type"] == "documentation" for gap in gaps)
    documentation_gap = next(gap for gap in gaps if gap["type"] == "documentation")
    assert documentation_gap["reference_claw"] == "nanobot"
    assert documentation_gap["reference_metrics"]["docstring_coverage_pct"] > 0
    assert documentation_gap["evidence"]["metric"] == "docstring_coverage_pct"


@pytest.mark.asyncio
async def test_comparator_handles_missing_reference_path_gracefully(tmp_path):
    comparator = ClawComparator(ref_path=tmp_path / "missing-ref")
    gaps = await comparator.find_gaps({"metrics": {"files": 1, "lines": 10}})
    assert gaps == []


@pytest.mark.asyncio
async def test_proposal_generator_creates_proposals():
    mock_provider = AsyncMock()
    mock_provider.think_json = AsyncMock(
        return_value={
            "title": "Optimize memory cache",
            "description": "Add LRU cache to memory retrieval",
            "impact_pct": 35,
            "risk": "low",
            "confidence_pct": 88,
            "estimated_hours": 1.5,
            "code_changes": {},
            "test_changes": {
                "tests/test_memory.py": "def test_cache():\n    assert True\n"
            },
        }
    )

    generator = ProposalGenerator(provider=mock_provider)
    gaps = [
        {
            "type": "performance",
            "description": "Memory retrieval is slow",
            "reference_claw": "nanobot",
            "self_metrics": {"lines": 10},
            "reference_metrics": {"lines": 25},
            "evidence": {"metric": "lines", "self": 10, "reference": 25, "delta": 15},
        }
    ]
    proposals = await generator.generate(gaps)
    assert len(proposals) == 1
    assert proposals[0].title == "Optimize memory cache"
    assert proposals[0].confidence_pct == 88
    assert proposals[0].test_changes == {
        "tests/test_memory.py": "def test_cache():\n    assert True\n"
    }
    prompt = mock_provider.think_json.await_args.kwargs["prompt"]
    assert "test_changes" in prompt
    assert "reference_metrics" in prompt
    assert "comparison_evidence" in prompt


@pytest.mark.asyncio
async def test_proposal_generator_handles_bad_json():
    mock_provider = AsyncMock()
    mock_provider.think_json = AsyncMock(side_effect=ValueError("bad json"))

    generator = ProposalGenerator(provider=mock_provider)
    gaps = [
        {
            "type": "test_coverage",
            "description": "Missing tests",
            "reference_claw": "nanobot",
            "self_metrics": {},
        }
    ]
    proposals = await generator.generate(gaps)
    assert len(proposals) == 0  # gracefully returns empty list


@pytest.mark.asyncio
async def test_proposal_generator_defaults_missing_test_changes():
    mock_provider = AsyncMock()
    mock_provider.think_json = AsyncMock(
        return_value={
            "title": "Add tests later",
            "description": "Backward compatible response.",
            "impact_pct": 10,
            "risk": "low",
            "confidence_pct": 70,
            "estimated_hours": 1.0,
            "code_changes": {"kinclaw/example.py": "pass\n"},
        }
    )

    generator = ProposalGenerator(provider=mock_provider)
    proposals = await generator.generate(
        [
            {
                "type": "test_coverage",
                "description": "Missing tests",
                "reference_claw": "nanobot",
                "self_metrics": {},
            }
        ]
    )

    assert len(proposals) == 1
    assert proposals[0].test_changes == {}
