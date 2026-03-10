"""Global configuration via pydantic-settings (reads from .env)."""
from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AI — provider: "claude" | "gemini"
    provider: str = "claude"
    anthropic_api_key: str = "not-set"
    claude_model: str = "claude-sonnet-4-6"
    gemini_api_key: str = "not-set"
    gemini_model: str = "gemini-2.5-flash"

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_ids: str = ""

    # Discord
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    discord_guild_id: str = ""

    # GitHub
    github_token: str = "not-set"
    github_repo: str = "owner/kinclaw"
    github_default_branch: str = "main"

    # Behavior
    sleep_between_analyses: int = 3600
    max_proposals_per_day: int = 3
    auto_merge_confidence: int = 98

    # Guardrails
    monthly_budget_usd: float = 100.0
    max_commits_per_day: int = 10
    posts_per_day: int = 2

    # Database
    database_url: str = "sqlite+aiosqlite:///./kinclaw.db"

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # Channels — stored as comma-separated string to avoid pydantic-settings
    # trying json.loads() on plain values like "telegram,discord"
    active_channels: str = "telegram"

    @property
    def active_channels_list(self) -> list[str]:
        return [c.strip() for c in self.active_channels.split(",") if c.strip()]

    @property
    def telegram_allowed_id_list(self) -> list[int]:
        if not self.telegram_allowed_ids:
            return []
        return [int(x.strip()) for x in self.telegram_allowed_ids.split(",") if x.strip()]


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return (cached) global settings instance."""
    return Settings()
