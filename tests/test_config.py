import pytest
from kinclaw.config import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.claude_model == "claude-sonnet-4-6"
    assert s.sleep_between_analyses == 3600
    assert s.max_proposals_per_day == 3
    assert s.monthly_budget_usd == 100


def test_settings_channels_list():
    s = Settings(active_channels="telegram,discord")
    assert "telegram" in s.active_channels_list
    assert "discord" in s.active_channels_list


def test_get_settings_is_cached():
    # Clear lru_cache first
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()


def test_settings_id_parsing_helpers():
    s = Settings(
        telegram_allowed_ids="1, 2",
        discord_allowed_ids="10,20",
        telegram_default_chat_id="999",
        discord_channel_id="555",
    )
    assert s.telegram_allowed_id_list == [1, 2]
    assert s.discord_allowed_id_list == [10, 20]
    assert s.telegram_default_chat_id_int == 999
    assert s.discord_default_chat_id_int == 555
