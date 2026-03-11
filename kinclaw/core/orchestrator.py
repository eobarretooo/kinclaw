"""Orchestrates agent startup, channel registration, and graceful shutdown."""
from __future__ import annotations

import asyncio

from kinclaw.channels.router import ChannelRouter
from kinclaw.config import Settings
from kinclaw.core.agent import KinClawAgent
from kinclaw.core.bus import MessageBus
from kinclaw.database.connection import init_db
from kinclaw.logger import logger, setup_logging
from kinclaw.providers.base import LLMProvider


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bus = MessageBus()
        self._router: ChannelRouter | None = None
        self._agent: KinClawAgent | None = None

    async def start(self) -> None:
        setup_logging()
        logger.info("KinClaw orchestrator starting")

        await init_db(self._settings.database_url)

        provider = self._build_provider()

        self._router = ChannelRouter(self._bus)
        await self._register_channels()

        self._agent = KinClawAgent(
            settings=self._settings,
            provider=provider,
            bus=self._bus,
            router=self._router,
        )

        await self._router.start_all()
        await self._agent.run_forever()

    async def stop(self) -> None:
        logger.info("Graceful shutdown initiated")
        if self._agent:
            await self._agent.stop()
        if self._router:
            await self._router.stop_all()

    async def _register_channels(self) -> None:
        s = self._settings
        active = s.active_channels_list

        if "telegram" in active and s.telegram_bot_token:
            from kinclaw.channels.telegram import TelegramChannel
            ch = TelegramChannel(
                token=s.telegram_bot_token,
                allowed_ids=s.telegram_allowed_id_list,
                default_chat_id=s.telegram_default_chat_id_int,
                bus=self._bus,
            )
            self._router.register(ch)
            logger.info("Telegram channel registered")

        if "discord" in active and s.discord_bot_token:
            from kinclaw.channels.discord import DiscordChannel
            ch = DiscordChannel(
                token=s.discord_bot_token,
                channel_id=int(s.discord_channel_id or 0),
                allowed_ids=s.discord_allowed_id_list,
                default_chat_id=s.discord_default_chat_id_int,
                bus=self._bus,
            )
            self._router.register(ch)
            logger.info("Discord channel registered")

    def _build_provider(self) -> LLMProvider:
        s = self._settings
        if s.provider == "gemini":
            from kinclaw.providers.gemini import GeminiProvider
            logger.info("Using Gemini provider: {}", s.gemini_model)
            return GeminiProvider(api_key=s.gemini_api_key, model=s.gemini_model)
        from kinclaw.providers.claude import ClaudeProvider
        logger.info("Using Claude provider: {}", s.claude_model)
        return ClaudeProvider(api_key=s.anthropic_api_key, model=s.claude_model)

    @property
    def agent(self) -> KinClawAgent | None:
        return self._agent
