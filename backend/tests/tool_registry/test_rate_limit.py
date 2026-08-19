from datetime import UTC, datetime, timedelta

from app.tool_registry.rate_limit import InMemoryFixedWindowRateLimiter, rate_limit_key


def test_fixed_window_blocks_sixty_first_call() -> None:
    limiter = InMemoryFixedWindowRateLimiter()
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)

    assert all(limiter.check("v1:t1", 60, now).allowed for _ in range(60))

    denied = limiter.check("v1:t1", 60, now)

    assert denied.allowed is False
    assert denied.retry_after_seconds == 60


def test_window_resets_at_next_utc_minute_boundary() -> None:
    limiter = InMemoryFixedWindowRateLimiter()
    now = datetime(2026, 8, 19, 10, 0, 30, tzinfo=UTC)

    assert limiter.check("v1:t1", 1, now).allowed is True

    denied = limiter.check("v1:t1", 1, now)

    assert denied.allowed is False
    assert denied.retry_after_seconds == 30
    assert limiter.check("v1:t1", 1, now + timedelta(seconds=30)).allowed is True


def test_rate_limit_key_uses_internal_sentinel_without_tenant() -> None:
    assert rate_limit_key(version_id=12, tenant_id=None) == "12:__internal__"
    assert rate_limit_key(version_id=12, tenant_id="tenant-a") == "12:tenant-a"
