"""KinClaw autonomous agent — the main brain."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from datetime import datetime, timedelta
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
from kinclaw.core.types import Approval, InboundMessage, Proposal, ProposalStatus
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
        self._approval_queue = ApprovalQueue(persist_decisions=True)
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
        self._state.error = None
        self._state.last_cycle_started_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        logger.info("Starting improvement cycle")
        await self._audit.log("cycle_start")
        proposal: Proposal | None = None

        try:
            await self._process_pending_proposals()

            if self._state.proposals_today >= self._settings.max_proposals_per_day:
                logger.info(
                    "Daily proposal limit reached ({}), sleeping",
                    self._settings.max_proposals_per_day,
                )
                return

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
            await self._save_proposal(proposal, status=ProposalStatus.PENDING)

            # 4. Notify owner
            notify_text = self._format_proposal_notification(proposal)
            await self.broadcast(notify_text)
            await self._update_proposal_status(proposal.id, ProposalStatus.SENT)
            self._approval_queue.register_proposal(proposal.id)
            logger.info(
                "Proposal sent: {} (confidence: {}%)",
                proposal.title,
                proposal.confidence_pct,
            )

            approval = await self._approval_queue.get_for(proposal.id, timeout=0)
            if approval is not None:
                await self._process_approval_decision(proposal, approval)
        except Exception as exc:
            self._state.error = str(exc)
            if proposal is not None:
                await self._mark_proposal_failed(proposal.id, str(exc))
            raise
        finally:
            self._state.current_proposal_id = None
            self._state.phase = AgentPhase.IDLE
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
        pending_proposal_ids = await self._pending_approval_proposal_ids()
        if not pending_proposal_ids:
            return
        approval = self._approval_parser.parse(
            message=msg.content,
            pending_proposal_ids=pending_proposal_ids,
            channel=msg.channel,
        )
        if approval:
            await self._approval_queue.submit(approval)

    async def _process_pending_proposals(self) -> None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            pending_records = await repo.list_by_statuses(
                [ProposalStatus.PENDING, ProposalStatus.SENT]
            )

        for record in reversed(pending_records):
            proposal = await self._load_proposal(record.id)
            if proposal is None:
                continue

            if self._is_timed_out(proposal.created_at):
                await self.broadcast(
                    f"⏰ Proposal timed out with no response: {proposal.title}"
                )
                await self._update_proposal_status(
                    proposal.id, ProposalStatus.TIMED_OUT
                )
                await self._approval_queue.forget(proposal.id)
                logger.info("Proposal {} timed out", proposal.id)
                continue

            approval = await self._approval_queue.peek_for(proposal.id)
            if approval is None:
                continue

            try:
                await self._process_approval_decision(proposal, approval)
            except Exception as exc:
                await self._mark_proposal_failed(proposal.id, str(exc))
                raise

    async def _process_approval_decision(
        self, proposal: Proposal, approval: Approval
    ) -> None:
        await self._update_proposal_status(
            proposal.id,
            ProposalStatus.APPROVED if approval.approved else ProposalStatus.REJECTED,
        )
        if approval.approved:
            self._state.phase = AgentPhase.EXECUTING
            self._publish_state()
            await self._update_proposal_status(proposal.id, ProposalStatus.EXECUTING)
        else:
            self._state.phase = AgentPhase.REPORTING
            self._publish_state()

        result = await self._executor.execute(
            proposal, approval, notify_fn=self.broadcast
        )

        self._state.phase = AgentPhase.REPORTING
        self._publish_state()
        if result.get("success"):
            await self._audit.log("cycle_success", detail=proposal.title)
            await self._update_proposal_status(proposal.id, ProposalStatus.DONE)
        else:
            await self._audit.log(
                "cycle_failed",
                detail=str(result.get("reason")),
                result="failed",
            )
            await self._update_proposal_status(
                proposal.id,
                ProposalStatus.REJECTED
                if result.get("reason") == "rejected"
                else ProposalStatus.PR_FAILED
                if result.get("reason") == "pr_failed"
                else ProposalStatus.FAILED,
            )
        await self._approval_queue.forget(proposal.id)

    def _is_timed_out(self, created_at: datetime) -> bool:
        return datetime.utcnow() - created_at >= timedelta(hours=1)

    async def _load_proposal(self, proposal_id: str) -> Proposal | None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            record = await repo.get(proposal_id)
            if record is None:
                return None
            return repo.to_proposal(record)

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
            f"Proposal ID: `{proposal.id}`\n"
            f"Reply **aprova {proposal.id}** to approve or **nega {proposal.id}** to reject.\n"
            f"(Timeout in 1 hour)"
        )

    @property
    def state(self) -> AgentState:
        return self._state

    def _publish_state(self) -> None:
        if self._state_publisher is not None:
            self._state_publisher(self._state.to_dict())

    async def _save_proposal(
        self, proposal: Proposal, status: ProposalStatus = ProposalStatus.PENDING
    ) -> None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            await repo.save_proposal(proposal, status=status)

    async def _update_proposal_status(
        self, proposal_id: str, status: ProposalStatus
    ) -> None:
        async with get_session() as session:
            repo = ProposalRepo(session)
            await repo.update_status(proposal_id, status)

    async def _mark_proposal_failed(self, proposal_id: str, detail: str) -> None:
        await self._audit.log("cycle_failed", detail=detail, result="failed")
        await self._update_proposal_status(proposal_id, ProposalStatus.FAILED)
        await self._approval_queue.forget(proposal_id)

    async def _pending_approval_proposal_ids(self) -> list[str]:
        pending_ids = set(self._approval_queue.pending_ids())
        async with get_session() as session:
            repo = ProposalRepo(session)
            pending_records = await repo.list_by_statuses(
                [ProposalStatus.PENDING, ProposalStatus.SENT]
            )
        pending_ids.update(record.id for record in pending_records)
        return list(pending_ids)
