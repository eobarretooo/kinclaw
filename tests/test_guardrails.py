import pytest
from kinclaw.guardrails.limits import RateLimiter
from kinclaw.guardrails.safety import SafetyChecker


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_commits_per_day=10, max_posts_per_day=2)
    assert await limiter.can_commit() is True
    await limiter.record_commit()
    assert limiter.commits_today() == 1


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_exceeded():
    limiter = RateLimiter(max_commits_per_day=2, max_posts_per_day=2)
    await limiter.record_commit()
    await limiter.record_commit()
    assert await limiter.can_commit() is False


@pytest.mark.asyncio
async def test_rate_limiter_posts():
    limiter = RateLimiter(max_commits_per_day=10, max_posts_per_day=1)
    assert await limiter.can_post() is True
    await limiter.record_post()
    assert await limiter.can_post() is False


def test_safety_checker_blocks_forbidden_paths():
    checker = SafetyChecker()
    assert checker.is_safe_path("kinclaw/core/agent.py") is True
    assert checker.is_safe_path("kinclaw/guardrails/safety.py") is False
    assert checker.is_safe_path("kinclaw/approval/queue.py") is False
    assert checker.is_safe_path(".env") is False


def test_safety_checker_allows_normal_paths():
    checker = SafetyChecker()
    assert checker.is_safe_path("kinclaw/skills/builtin/new_skill.py") is True
    assert checker.is_safe_path("kinclaw/core/agent.py") is True


def test_safety_checker_validates_changes():
    checker = SafetyChecker()
    violations = checker.validate_proposal_changes({
        "kinclaw/guardrails/safety.py": "# safe content",
    })
    assert len(violations) == 1
    assert "Forbidden path" in violations[0]


def test_safety_checker_blocks_dangerous_content():
    checker = SafetyChecker()
    violations = checker.validate_proposal_changes({
        "kinclaw/core/new_module.py": "os.system('rm -rf /')",
    })
    assert len(violations) == 1
    assert "Dangerous content" in violations[0]
