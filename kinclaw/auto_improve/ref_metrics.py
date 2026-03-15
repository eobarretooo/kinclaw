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
        if not (claw_dir / "kinclaw").exists():
            continue
        analysis = await SelfAnalyzer(base_path=claw_dir).analyze()
        metrics_by_claw[claw_dir.name] = analysis.get("metrics", {})
    return metrics_by_claw
