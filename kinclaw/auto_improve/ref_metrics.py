"""Helpers for collecting metrics from reference claws."""

from __future__ import annotations

from pathlib import Path

from kinclaw.auto_improve.analyzer import SelfAnalyzer


async def collect_reference_metrics(ref_path: Path) -> dict[str, dict]:
    """Analyze each reference claw directory that contains code."""
    if not ref_path.exists() or not ref_path.is_dir():
        return {}

    metrics_by_claw: dict[str, dict] = {}
    for claw_dir in sorted(path for path in ref_path.iterdir() if path.is_dir()):
        analysis = await SelfAnalyzer(base_path=claw_dir).analyze()
        metrics = analysis.get("metrics", {})
        if metrics.get("files", 0) <= 0:
            continue
        metrics_by_claw[claw_dir.name] = metrics
    return metrics_by_claw
