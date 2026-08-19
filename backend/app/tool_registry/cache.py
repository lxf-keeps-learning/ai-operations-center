from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from app.core.logging.logger import get_logger
from app.tool_center.exceptions import RegistryUnavailableError
from app.tool_registry.contracts import RegistrySnapshot

logger = get_logger("ioc.tool_registry")

_Clock = Callable[[], datetime]


def age_seconds(loaded_at: datetime, now: datetime) -> float:
    """计算快照年龄；朴素时间按 UTC 解释，带时区时间统一转换到 UTC。"""
    return (_to_aware_utc(now) - _to_aware_utc(loaded_at)).total_seconds()


def _to_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RegistryCache:
    """进程内只读配置缓存与最近稳定快照。

    - 普通缓存默认 30 秒 TTL，过期后从 loader 重新加载；
    - loader 失败时抛出 RegistryUnavailableError，由上层按快照规则降级；
    - 每次成功加载同时更新稳定快照，稳定快照只通过 get_stable_fallback 读取。
    """

    def __init__(
        self,
        *,
        ttl_seconds: int,
        stale_query_ttl_seconds: int,
        clock: _Clock | None = None,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        if stale_query_ttl_seconds < ttl_seconds:
            raise ValueError("stale_query_ttl_seconds must not be smaller than ttl_seconds")
        self._ttl_seconds = ttl_seconds
        self._stale_query_ttl_seconds = stale_query_ttl_seconds
        self._clock = clock or _utc_now
        self._lock = Lock()
        self._current: RegistrySnapshot | None = None
        self._stable_fallback: RegistrySnapshot | None = None

    def get_or_load(self, loader: Callable[[], RegistrySnapshot]) -> RegistrySnapshot:
        now = self._clock()
        with self._lock:
            current = self._current
            if current is not None and age_seconds(current.loaded_at, now) <= self._ttl_seconds:
                return current
            try:
                snapshot = loader()
            except Exception as exc:
                raise RegistryUnavailableError(
                    "tool registry database unavailable",
                    detail={"cause": type(exc).__name__},
                ) from exc
            self._current = snapshot
            self._stable_fallback = snapshot
            return snapshot

    def get_stable_fallback(self, now: datetime) -> RegistrySnapshot:
        with self._lock:
            fallback = self._stable_fallback
            if fallback is None or age_seconds(fallback.loaded_at, now) > self._stale_query_ttl_seconds:
                raise RegistryUnavailableError(
                    "tool registry stable snapshot unavailable"
                )
            return fallback

    def invalidate(self) -> None:
        """清除普通缓存，强制下次访问从 loader 重新加载；保留稳定快照用于降级。"""
        with self._lock:
            self._current = None
