import asyncio
import pytest
from kinclaw.channels.base import BaseChannel
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import OutboundMessage


class FakeChannel(BaseChannel):
    name = "fake"
    sent: list = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


def test_is_allowed_wildcard():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    assert ch.is_allowed("anyone") is True


def test_is_allowed_list():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["123", "456"]}, bus=bus)
    assert ch.is_allowed("123") is True
    assert ch.is_allowed("999") is False


def test_is_allowed_empty_denies_all():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": []}, bus=bus)
    assert ch.is_allowed("anyone") is False


@pytest.mark.asyncio
async def test_handle_message_publishes_to_bus():
    bus = MessageBus()
    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    await ch._handle_message("u1", "c1", "hello")
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=0.5)
    assert msg.content == "hello"
    assert msg.channel == "fake"


from kinclaw.channels.router import ChannelRouter


@pytest.mark.asyncio
async def test_router_routes_outbound():
    bus = MessageBus()
    router = ChannelRouter(bus)

    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    ch.sent = []
    router.register(ch)

    out = OutboundMessage(channel="fake", chat_id="c1", content="routed message")
    await bus.publish_outbound(out)
    await asyncio.sleep(0.05)

    assert len(ch.sent) == 1
    assert ch.sent[0].content == "routed message"


def test_router_register_and_get():
    bus = MessageBus()
    router = ChannelRouter(bus)
    ch = FakeChannel(config={"allow_from": ["*"]}, bus=bus)
    router.register(ch)
    assert router.get_channel("fake") is not None
    assert "fake" in router.channel_names


@pytest.mark.asyncio
async def test_router_broadcast_uses_default_chat_id():
    bus = MessageBus()
    router = ChannelRouter(bus)

    ch = FakeChannel(config={"allow_from": ["*"], "default_chat_id": "chat-1"}, bus=bus)
    ch.sent = []
    router.register(ch)

    await router.broadcast("hello default")

    assert len(ch.sent) == 1
    assert ch.sent[0].chat_id == "chat-1"
    assert ch.sent[0].content == "hello default"
