import asyncio
import pytest
from kinclaw.core.bus import MessageBus
from kinclaw.core.types import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_publish_and_consume_inbound():
    bus = MessageBus()
    msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="hello")
    await bus.publish_inbound(msg)
    consumed = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert consumed.content == "hello"


@pytest.mark.asyncio
async def test_publish_outbound_triggers_subscriber():
    bus = MessageBus()
    received = []

    async def handler(msg: OutboundMessage):
        received.append(msg)

    bus.subscribe_outbound(handler)
    out = OutboundMessage(channel="test", chat_id="c1", content="bye")
    await bus.publish_outbound(out)
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].content == "bye"
