"""Compares KinClaw metrics against the 7 reference Claws."""

from __future__ import annotations

from pathlib import Path

from kinclaw.auto_improve.ref_metrics import collect_reference_metrics
from kinclaw.logger import logger

IMPROVEMENT_SIGNALS = [
    {
        "type": "documentation",
        "description": "Add or improve docstrings where reference claws are more documented",
        "metric": "docstring_coverage_pct",
        "minimum_delta": 10.0,
    },
    {
        "type": "test_coverage",
        "description": "Add tests to match stronger reference validation coverage",
        "metric": "test_file_ratio",
        "minimum_delta": 0.15,
    },
    {
        "type": "async_patterns",
        "description": "Adopt async patterns used in reference claws",
        "metric": "async_function_ratio",
        "minimum_delta": 0.15,
    },
]


class ClawComparator:
    def __init__(self, ref_path: Path = Path("ref")) -> None:
        self._ref = ref_path

    async def find_gaps(self, self_analysis: dict) -> list[dict]:
        """Identify improvement gaps by comparing self with reference claws."""
        if not self._ref.exists():
            logger.info("ClawComparator: no reference path at {}", self._ref)
            return []

        gaps: list[dict] = []
        metrics = self_analysis.get("metrics", {})
        reference_metrics = await collect_reference_metrics(self._ref)
        if not reference_metrics:
            logger.info(
                "ClawComparator: no reference metrics available in {}", self._ref
            )
            return []

        for signal in IMPROVEMENT_SIGNALS:
            best_gap = self._find_best_gap(
                signal=signal, self_metrics=metrics, reference_metrics=reference_metrics
            )
            if best_gap:
                gaps.append(best_gap)

        selected = sorted(gaps, key=lambda gap: gap["evidence"]["delta"], reverse=True)[
            :3
        ]
        logger.info(
            "ClawComparator: found {} gaps (returning top {})", len(gaps), len(selected)
        )
        return selected

    def _find_best_gap(
        self, signal: dict, self_metrics: dict, reference_metrics: dict[str, dict]
    ) -> dict | None:
        metric_name = signal["metric"]
        best_gap: dict | None = None
        self_value = float(self_metrics.get(metric_name, 0) or 0)

        for claw_name, claw_metrics in reference_metrics.items():
            reference_value = float(claw_metrics.get(metric_name, 0) or 0)
            delta = round(reference_value - self_value, 1)
            if delta < signal["minimum_delta"]:
                continue

            candidate = {
                "type": signal["type"],
                "description": signal["description"],
                "reference_claw": claw_name,
                "self_metrics": self_metrics,
                "reference_metrics": claw_metrics,
                "evidence": {
                    "metric": metric_name,
                    "self": self_value,
                    "reference": reference_value,
                    "delta": delta,
                },
            }
            if (
                best_gap is None
                or candidate["evidence"]["delta"] > best_gap["evidence"]["delta"]
            ):
                best_gap = candidate

        return best_gap
