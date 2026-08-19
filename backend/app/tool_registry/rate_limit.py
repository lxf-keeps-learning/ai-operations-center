from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import math
from threading import Lock


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None


class RateLimiter:
    def check(self, key: str, limit: int, now: datetime) -> RateLimitDecision:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryFixedWindowRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict[str, tuple[datetime, int]] = {}

    def check(self, key: str, limit: int, now: datetime) -> RateLimitDecision:
        if limit < 1:
            raise ValueError("limit must be positive")

        current = now.astimezone(UTC)
        window_start = current.replace(second=0, microsecond=0)
        next_boundary = window_start + timedelta(minutes=1)

        with self._lock:
            stored_window_start, count = self._state.get(key, (window_start, 0))
            if stored_window_start != window_start:
                stored_window_start = window_start
                count = 0

            if count >= limit:
                retry_after = max(1, math.ceil((next_boundary - current).total_seconds()))
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

            self._state[key] = (stored_window_start, count + 1)
            return RateLimitDecision(allowed=True, retry_after_seconds=None)


def rate_limit_key(version_id: int, tenant_id: str | None) -> str:
    return f"{version_id}:{tenant_id or '__internal__'}"
