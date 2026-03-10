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
