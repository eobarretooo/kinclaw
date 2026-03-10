"""Abstract base class for all channel adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from kinclaw.core.bus import MessageBus
from kinclaw.core.types import InboundMessage, OutboundMessage
from kinclaw.logger import logger


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Connect and start listening for messages."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect and clean up."""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Deliver an outbound message."""

    def is_allowed(self, sender_id: str) -> bool:
        """Check sender against allowlist. Empty list → deny all; '*' → allow all."""
        allow = self.config.get("allow_from", []) if isinstance(self.config, dict) else getattr(self.config, "allow_from", [])
        if not allow:
            logger.warning("{}: allow_from is empty — denying sender {}", self.name, sender_id)
            return False
        if "*" in allow:
            return True
        return str(sender_id) in [str(a) for a in allow]

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_allowed(sender_id):
            logger.warning("{}: denied sender {}", self.name, sender_id)
            return
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(msg)

    @property
    def is_running(self) -> bool:
        return self._running
