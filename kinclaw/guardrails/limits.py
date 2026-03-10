"""Rate limiters for commits, posts, and budget."""
from __future__ import annotations

from collections import defaultdict
from datetime import date


class RateLimiter:
    def __init__(
        self,
        max_commits_per_day: int = 10,
        max_posts_per_day: int = 2,
        monthly_budget_usd: float = 100.0,
    ) -> None:
        self._max_commits = max_commits_per_day
        self._max_posts = max_posts_per_day
        self._budget = monthly_budget_usd
        self._commits: dict[date, int] = defaultdict(int)
        self._posts: dict[date, int] = defaultdict(int)
        self._spend: dict[str, float] = defaultdict(float)  # YYYY-MM → USD

    async def can_commit(self) -> bool:
        return self._commits[date.today()] < self._max_commits

    async def record_commit(self) -> None:
        self._commits[date.today()] += 1

    async def can_post(self) -> bool:
        return self._posts[date.today()] < self._max_posts

    async def record_post(self) -> None:
        self._posts[date.today()] += 1

    async def can_spend(self, usd: float) -> bool:
        month_key = date.today().strftime("%Y-%m")
        return self._spend[month_key] + usd <= self._budget

    async def record_spend(self, usd: float) -> None:
        month_key = date.today().strftime("%Y-%m")
        self._spend[month_key] += usd

    def commits_today(self) -> int:
        return self._commits[date.today()]

    def posts_today(self) -> int:
        return self._posts[date.today()]
