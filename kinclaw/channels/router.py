"""Routes outbound messages to the correct channel adapter."""
from __future__ import annotations

import asyncio

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class ChannelRouter:
    """Manages all channel adapters and routes outbound messages."""

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus
        self._channels: dict[str, BaseChannel] = {}
        self._bus.subscribe_outbound(self._route_outbound)

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel
        logger.info("Channel registered: {}", channel.name)

    async def start_all(self) -> None:
        tasks = [ch.start() for ch in self._channels.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ch, result in zip(self._channels.values(), results):
            if isinstance(result, Exception):
                logger.error("Channel {} failed to start: {}", ch.name, result)

    async def stop_all(self) -> None:
        for ch in self._channels.values():
            try:
                await ch.stop()
            except Exception:
                logger.exception("Error stopping channel {}", ch.name)

    async def broadcast(self, content: str, chat_ids: dict[str, str] | None = None) -> None:
        """Send same message to all registered channels.

        Args:
            content: Message text to broadcast
            chat_ids: Optional dict mapping channel_name -> chat_id for targeting specific chats.
                     If None, channels with a 'default_chat_id' config will receive the message.
        """
        for name, ch in self._channels.items():
            chat_id = None
            if chat_ids:
                chat_id = chat_ids.get(name)
            else:
                cfg = ch.config
                chat_id = (cfg.get("default_chat_id") if isinstance(cfg, dict)
                          else getattr(cfg, "default_chat_id", None))

            if not chat_id:
                logger.debug("No default_chat_id for channel {}, skipping broadcast", name)
                continue

            out = OutboundMessage(channel=name, chat_id=str(chat_id), content=content)
            try:
                await ch.send(out)
            except Exception:
                logger.exception("Broadcast error on channel {}", name)

    async def _route_outbound(self, msg: OutboundMessage) -> None:
        ch = self._channels.get(msg.channel)
        if ch:
            await ch.send(msg)
        else:
            logger.warning("No channel registered for: {}", msg.channel)

    def get_channel(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)

    @property
    def channel_names(self) -> list[str]:
        return list(self._channels.keys())
