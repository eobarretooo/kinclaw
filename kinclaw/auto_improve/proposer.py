"""Generates concrete improvement proposals using Claude."""

from __future__ import annotations

import json

from kinclaw.core.types import Proposal
from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


_PROPOSAL_SYSTEM = """You are KinClaw's self-improvement engine.
Given a gap in the codebase, generate a concrete, actionable improvement proposal.
Be specific. The proposal must include actual code changes (small, focused).
Respond with valid JSON only."""

_PROPOSAL_PROMPT_TEMPLATE = """KinClaw found this improvement opportunity:

Gap type: {gap_type}
Description: {description}
Reference claw: {reference_claw}
Current metrics: {metrics}
reference_metrics: {reference_metrics}
comparison_evidence: {comparison_evidence}

Generate a focused improvement proposal. Respond with JSON:
{{
  "title": "Short action title (max 60 chars)",
  "description": "2-3 sentences explaining the improvement",
  "impact_pct": <integer 1-100>,
  "risk": "low|medium|high",
  "confidence_pct": <integer 0-100>,
  "estimated_hours": <float>,
  "code_changes": {{
    "kinclaw/path/to/file.py": "full file content here"
  }},
  "test_changes": {{
    "tests/path/to/test_file.py": "full file content here"
  }}
}}
Keep code_changes and test_changes small (1-2 files each, focused changes).
"""


class ProposalGenerator:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(self, gaps: list[dict]) -> list[Proposal]:
        proposals = []
        for gap in gaps:
            try:
                proposal = await self._generate_one(gap)
                if proposal:
                    proposals.append(proposal)
            except Exception as e:
                logger.error(
                    "Failed to generate proposal for gap {}: {}", gap.get("type"), e
                )
        return proposals

    async def _generate_one(self, gap: dict) -> Proposal | None:
        prompt = _PROPOSAL_PROMPT_TEMPLATE.format(
            gap_type=gap.get("type", ""),
            description=gap.get("description", ""),
            reference_claw=gap.get("reference_claw", ""),
            metrics=json.dumps(gap.get("self_metrics", {})),
            reference_metrics=json.dumps(gap.get("reference_metrics", {})),
            comparison_evidence=json.dumps(gap.get("evidence", {})),
        )
        try:
            data = await self._provider.think_json(
                prompt=prompt, system=_PROPOSAL_SYSTEM
            )
            return Proposal(
                title=data.get("title", "Untitled improvement"),
                description=data.get("description", ""),
                impact_pct=int(data.get("impact_pct", 0)),
                risk=data.get("risk", "low"),
                confidence_pct=int(data.get("confidence_pct", 0)),
                estimated_hours=float(data.get("estimated_hours", 1.0)),
                code_changes=data.get("code_changes", {}),
                test_changes=data.get("test_changes", {}),
                reference_claw=gap.get("reference_claw", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Invalid proposal JSON: {}", e)
            return None
