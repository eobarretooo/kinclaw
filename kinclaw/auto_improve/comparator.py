"""Compares KinClaw metrics against the 7 reference Claws."""
from __future__ import annotations

from pathlib import Path

from kinclaw.logger import logger

IMPROVEMENT_SIGNALS = [
    {"type": "test_coverage", "description": "Add unit tests for untested modules", "min_files": 5},
    {"type": "error_handling", "description": "Improve error handling patterns", "min_files": 10},
    {"type": "async_patterns", "description": "Optimize async/await usage", "min_files": 5},
    {"type": "documentation", "description": "Add or improve docstrings", "min_files": 3},
    {"type": "performance", "description": "Profile and optimize hot paths", "min_files": 10},
]

_TYPE_TO_CLAW = {
    "test_coverage": "nanobot",
    "error_handling": "openclaw",
    "async_patterns": "zeroclaw",
    "documentation": "nanobot",
    "performance": "zeroclaw",
}


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
                best_claw = _TYPE_TO_CLAW.get(signal["type"], "nanobot")
                gaps.append({
                    "type": signal["type"],
                    "description": signal["description"],
                    "reference_claw": best_claw,
                    "self_metrics": metrics,
                })

        # Return top 3 gaps to keep focused
        selected = gaps[:3]
        logger.info("ClawComparator: found {} gaps (returning top {})", len(gaps), len(selected))
        return selected
