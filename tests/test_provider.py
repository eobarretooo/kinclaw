import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kinclaw.providers.claude import ClaudeProvider


@pytest.mark.asyncio
async def test_think_returns_string():
    """think() calls Claude API and returns text."""
    mock_content = MagicMock()
    mock_content.text = "Paris is the capital."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.think("What is the capital of France?")

    assert "Paris" in result


@pytest.mark.asyncio
async def test_think_json_parses_response():
    """think_json() returns parsed dict."""
    mock_content = MagicMock()
    mock_content.text = '{"answer": "Paris"}'
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.think_json("What is the capital?")

    assert result["answer"] == "Paris"
