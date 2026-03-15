"""KinClaw autonomous agent — the main brain."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from kinclaw.auto_improve.analyzer import SelfAnalyzer
from kinclaw.auto_improve.comparator import ClawComparator
from kinclaw.auto_improve.proposer import ProposalGenerator
from kinclaw.approval.executor import ApprovalExecutor
from kinclaw.approval.parser import ApprovalParser
from kinclaw.approval.queue import ApprovalQueue
from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.bus import MessageBus
from kinclaw.core.state import AgentPhase, AgentState
from kinclaw.core.types import InboundMessage, Proposal
from kinclaw.database.connection import get_session
from kinclaw.database.queries import ProposalRepo
from kinclaw.guardrails.audit import AuditLogger
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker
from kinclaw.logger import logger
from kinclaw.providers.base import LLMProvider


class KinClawAgent:
    """Autonomous self-improving agent. Runs forever."""

    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        bus: MessageBus,
        router: ChannelRouter,
        state_publisher: Callable[[dict], None] | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._bus = bus
        self._router = router
        self._state = AgentState()
        self._state_publisher = state_publisher

        # Sub-systems
        self._analyzer = SelfAnalyzer(base_path=Path("."))
        self._comparator = ClawComparator(ref_path=Path("ref"))
        self._proposer = ProposalGenerator(provider=provider)
        self._approval_queue = ApprovalQueue()
        self._approval_parser = ApprovalParser()
        self._limiter = RateLimiter(
            max_commits_per_day=settings.max_commits_per_day,
            max_posts_per_day=settings.posts_per_day,
            monthly_budget_usd=settings.monthly_budget_usd,
        )
        self._safety = SafetyChecker()
        self._audit = AuditLogger()
        self._executor = ApprovalExecutor(
            safety=self._safety,
            limiter=self._limiter,
            audit=self._audit,
        )
        self._inbound_task: asyncio.Task | None = None
        self._publish_state()

    async def start_listening(self) -> None:
        """Start the inbound message listener task."""
        self._inbound_task = asyncio.create_task(self._listen_inbound())

    async def analyze_self(self) -> dict:
        """Analyze own codebase and return metrics + gaps."""
        self._state.phase = AgentPhase.ANALYZING
        self._publish_state()
        analysis = await self._analyzer.analyze()
        gaps = await self._comparator.find_gaps(analysis)
        analysis["gaps"] = gaps
        self._state.last_analysis_metrics = analysis.get("metrics", {})
        self._publish_state()
        return analysis

    async def propose_improvements(self, analysis: dict) -> list[Proposal]:
        """Generate improvement proposals from analysis gaps."""
        self._state.phase = AgentPhase.PROPOSING
        self._publish_state()
        gaps = analysis.get("gaps", [])
        if not gaps:
            logger.info("No gaps found in this analysis cycle")
            return []
        return await self._proposer.generate(gaps)

    async def broadcast(self, message: str) -> None:
        """Send message to all active channels."""
        await self._router.broadcast(message)

    async def run_improvement_cycle(self) -> None:
        """One complete analyze → propose → approve → execute cycle."""
        self._state.reset_daily_counters_if_new_day()

        if self._state.proposals_today >= self._settings.max_proposals_per_day:
            logger.info(
                "Daily proposal limit reached ({}), sleeping",
                self._settings.max_proposals_per_day,
            )
            return

        logger.info("Starting improvement cycle")
        await self._audit.log("cycle_start")

        # 1. Analyze
        analysis = await self.analyze_self()
        logger.info(
            "Analysis complete: {} files, {} lines, {} gaps",
            analysis["metrics"]["files"],
            analysis["metrics"]["lines"],
            len(analysis.get("gaps", [])),
        )

        # 2. Generate proposals
        proposals = await self.propose_improvements(analysis)
        if not proposals:
            logger.info("No proposals generated this cycle")
            self._state.phase = AgentPhase.IDLE
            self._publish_state()
            return

        # 3. Take best proposal (highest confidence)
        proposals.sort(key=lambda p: p.confidence_pct, reverse=True)
        proposal = proposals[0]
        self._state.proposals_today += 1
        self._state.current_proposal_id = proposal.id
        self._state.phase = AgentPhase.AWAITING_APPROVAL
        self._publish_state()
        await self._save_proposal(proposal, status="pending")

        # 4. Notify owner
        notify_text = self._format_proposal_notification(proposal)
        await self.broadcast(notify_text)
        logger.info(
            "Proposal sent: {} (confidence: {}%)",
            proposal.title,
            proposal.confidence_pct,
        )

        # 5. Wait for approval
        self._approval_queue.register_proposal(proposal.id)
        approval = await self._approval_queue.get_for(proposal.id, timeout=3600)

        if approval is None:
            await self.broadcast(
                f"⏰ Proposal timed out with no response: {proposal.title}"
            )
            logger.info("Proposal {} timed out", proposal.id)
            self._state.phase = AgentPhase.IDLE
            self._state.current_proposal_id = None
            self._publish_state()
            return

        # 6. Execute if approved
        await self._update_proposal_status(
            proposal.id, "approved" if approval.approved else "rejected"
        )
        if approval.approved:
            self._state.phase = AgentPhase.EXECUTING
            self._publish_state()
            await self._update_proposal_status(proposal.id, "executing")
        else:
            self._state.phase = AgentPhase.REPORTING
            self._publish_state()
        result = await self._executor.execute(
            proposal, approval, notify_fn=self.broadcast
        )

        # 7. Report
        self._state.phase = AgentPhase.REPORTING
        self._publish_state()
        if result.get("success"):
            await self._audit.log("cycle_success", detail=proposal.title)
            await self._update_proposal_status(proposal.id, "done")
        else:
            await self._audit.log(
                "cycle_failed",
                detail=str(result.get("reason")),
                result="failed",
            )
            await self._update_proposal_status(
                proposal.id,
                "rejected" if result.get("reason") == "rejected" else "failed",
            )

        self._state.phase = AgentPhase.IDLE
        self._state.current_proposal_id = None
        self._publish_state()

    async def run_forever(self) -> None:
        """Perpetual loop: cycle, sleep, repeat."""
        self._state.is_running = True
        self._publish_state()
        await self.start_listening()
        logger.info("KinClaw started — running forever")
        await self.broadcast("🤖 KinClaw is online and ready!")

        while self._state.is_running:
            try:
                await self.run_improvement_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unhandled error in improvement cycle")
                self._state.phase = AgentPhase.IDLE
                self._publish_state()

            if not self._state.is_running:
                break

            logger.info(
                "Sleeping {}s before next cycle", self._settings.sleep_between_analyses
            )
            await asyncio.sleep(self._settings.sleep_between_analyses)

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self._state.is_running = False
        self._publish_state()
        if self._inbound_task:
            self._inbound_task.cancel()
            try:
                await self._inbound_task
            except asyncio.CancelledError:
                pass
        await self.broadcast("👋 KinClaw is shutting down.")

    async def _listen_inbound(self) -> None:
        """Process inbound messages (approval responses)."""
        while True:
            try:
                msg: InboundMessage = await asyncio.wait_for(
                    self._bus.consume_inbound(), timeout=1.0
                )
                await self._handle_inbound(msg)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in inbound listener")

    async def _handle_inbound(self, msg: InboundMessage) -> None:
        """Route inbound messages to approval queue if relevant."""
        if not self._state.current_proposal_id:
            return
        approval = self._approval_parser.parse(
            message=msg.content,
            proposal_id=self._state.current_proposal_id,
            channel=msg.channel,
        )
        if approval:
            await self._approval_queue.submit(approval)

    def _format_proposal_notification(self, proposal: Proposal) -> str:
        return (
            f"🤖 KinClaw found an improvement opportunity!\n\n"
            f"📋 **{proposal.title}**\n\n"
            f"{proposal.description}\n\n"
            f"📊 Impact: +{proposal.impact_pct}%\n"
            f"⚠️ Risk: {proposal.risk.upper()}\n"
            f"💪 Confidence: {proposal.confidence_pct}%\n"
            f"⏱️ Estimated: {proposal.estimated_hours}h\n"
            f"🔍 Inspired by: {proposal.reference_claw}\n\n"
            f"Reply **aprova** to approve or **nega** to reject.\n"
            f"(Timeout in 1 hour)"
        )

    @property
    def state(self) -> AgentState:
        return self._state

    def _publish_state(self) -> None:
        if self._state_publisher is not None:
            self._state_publisher(self._state.to_dict())

    async def _save_proposal(self, proposal: Proposal, status: str = "pending") -> None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            await repo.save_proposal(proposal, status=status)

    async def _update_proposal_status(self, proposal_id: str, status: str) -> None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            await repo.update_status(proposal_id, status)
