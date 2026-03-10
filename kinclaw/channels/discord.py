"""Discord channel adapter using discord.py."""
from __future__ import annotations

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class DiscordChannel(BaseChannel):
    name = "discord"

    def __init__(self, token: str, channel_id: int, allowed_ids: list[int], bus: MessageBus) -> None:
        super().__init__(config={"allow_from": [str(i) for i in allowed_ids] or ["*"]}, bus=bus)
        self._token = token
        self._channel_id = channel_id
        self._client = None

    async def start(self) -> None:
        try:
            import discord
            intents = discord.Intents.default()
            intents.message_content = True
            self._client = discord.Client(intents=intents)

            channel_ref = self

            @self._client.event
            async def on_message(message):
                if message.author.bot:
                    return
                if message.channel.id != channel_ref._channel_id:
                    return
                await channel_ref._handle_message(
                    str(message.author.id),
                    str(message.channel.id),
                    message.content,
                )

            self._running = True
            logger.info("Discord channel starting")
            await self._client.start(self._token)
        except Exception as e:
            logger.error("Discord start error: {}", e)
            self._running = False

    async def stop(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.error("Discord stop error: {}", e)
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        if not self._client:
            logger.warning("Discord not started")
            return
        channel = self._client.get_channel(int(msg.chat_id))
        if channel:
            try:
                await channel.send(msg.content)
            except Exception as e:
                logger.error("Discord send error: {}", e)
