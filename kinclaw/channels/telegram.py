"""Telegram channel adapter using python-telegram-bot."""
from __future__ import annotations

from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage
from kinclaw.logger import logger


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, allowed_ids: list[int], bus: MessageBus) -> None:
        super().__init__(config={"allow_from": [str(i) for i in allowed_ids] or ["*"]}, bus=bus)
        self._token = token
        self._app = None

    async def start(self) -> None:
        try:
            from telegram.ext import Application, MessageHandler, filters
            self._app = Application.builder().token(self._token).build()
            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
            )
            self._running = True
            logger.info("Telegram channel starting")
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error("Telegram start error: {}", e)
            self._running = False

    async def stop(self) -> None:
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.error("Telegram stop error: {}", e)
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        if not self._app:
            logger.warning("Telegram not started, cannot send")
            return
        try:
            await self._app.bot.send_message(chat_id=int(msg.chat_id), text=msg.content)
        except Exception as e:
            logger.error("Telegram send error: {}", e)

    async def _on_message(self, update, context) -> None:
        if not update.message or not update.effective_user:
            return
        sender_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        content = update.message.text or ""
        await self._handle_message(sender_id, chat_id, content)
