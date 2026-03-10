"""Async message bus for inbound/outbound routing."""
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from kinclaw.core.types import InboundMessage, OutboundMessage
from kinclaw.logger import logger


OutboundHandler = Callable[[OutboundMessage], Awaitable[None]]


class MessageBus:
    """Central pub/sub queue bridging channels and the agent loop."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound_subs: list[OutboundHandler] = []

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self._inbound.get()

    def subscribe_outbound(self, handler: OutboundHandler) -> None:
        self._outbound_subs.append(handler)

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        for handler in self._outbound_subs:
            try:
                await handler(msg)
            except Exception:
                logger.exception("Outbound handler error for channel {}", msg.channel)
