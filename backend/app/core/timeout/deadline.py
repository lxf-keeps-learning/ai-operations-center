"""绝对 Deadline 与预算传播。

设计要点：
  - 使用单调时钟（time.monotonic），与挂钟调整无关。
  - Deadline 是"绝对截止时刻"；子层通过 child_timeout() 获得
    min(默认预算, 剩余总预算)，保证整个请求只有一个总预算。
  - deadline() 上下文管理器同时：
      1. 将 Deadline 注入 contextvars（供 Tool/LLM 层计算预算）；
      2. 用 asyncio.timeout 做真实执行约束。
    到期抛 TimeoutError（asyncio 语义）；用户主动取消抛 CancelledError，
    两者由调用方区分。
"""

from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar, Token
from typing import Callable, Optional

from app.core.timeout.errors import DeadlineExpiredError

Clock = Callable[[], float]


class Deadline:
    """单调时钟上的绝对截止时间。

    属性：
        deadline_at: 绝对截止时刻（单调时钟读数）。
        remaining_seconds: 剩余预算（>=0）。
        expired: 是否已过期。
    """

    __slots__ = ("deadline_at", "_clock")

    def __init__(self, seconds: float, *, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self.deadline_at = self._clock() + max(0.0, seconds)

    @classmethod
    def from_parent(
        cls,
        parent: "Deadline | None",
        seconds: float,
        *,
        clock: Clock = time.monotonic,
    ) -> "Deadline":
        """从父 Deadline 派生子 Deadline，取更早的截止时刻。"""
        child = cls(seconds, clock=clock)
        if parent is not None and parent.deadline_at < child.deadline_at:
            child.deadline_at = parent.deadline_at
        return child

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_at - self._clock())

    @property
    def expired(self) -> bool:
        return self.remaining_seconds <= 0.0

    def child_timeout(self, default_seconds: float) -> float:
        """子层预算：min(默认预算, 剩余总预算)。"""
        return min(max(0.0, default_seconds), self.remaining_seconds)

    def raise_if_expired(self, operation: str) -> None:
        if self.expired:
            raise DeadlineExpiredError(
                operation=operation,
                timeout_seconds=0.0,
                elapsed_ms=0,
                remaining_ms=0,
            )


_deadline_var: ContextVar[Optional[Deadline]] = ContextVar(
    "timeout_deadline",
    default=None,
)


def current_deadline() -> Deadline | None:
    """返回当前上下文中的 Deadline；没有则返回 None。"""
    return _deadline_var.get()


def child_timeout(default_seconds: float) -> float:
    """按当前 Deadline 计算子层预算；无 Deadline 时返回默认值。"""
    current = _deadline_var.get()
    if current is None:
        return max(0.0, default_seconds)
    return current.child_timeout(default_seconds)


class deadline:
    """异步上下文管理器：进入时建立 Deadline 并施加 asyncio.timeout。

    用法：
        async with deadline(settings.report_graph_timeout_seconds) as d:
            await graph.ainvoke(...)

    到期后抛出 TimeoutError（由 asyncio.timeout 负责执行约束），
    并可通过 current_deadline()/child_timeout() 查询剩余预算。
    """

    def __init__(
        self,
        seconds: float,
        *,
        operation: str | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        self._seconds = seconds
        self._operation = operation
        self._clock = clock
        self._deadline_obj: Deadline | None = None
        self._token: Token | None = None
        self._timeout_ctx: asyncio.timeout | None = None

    async def __aenter__(self) -> Deadline:
        parent = _deadline_var.get()
        self._deadline_obj = Deadline.from_parent(parent, self._seconds, clock=self._clock)
        self._token = _deadline_var.set(self._deadline_obj)
        self._timeout_ctx = asyncio.timeout(self._deadline_obj.remaining_seconds)
        try:
            await self._timeout_ctx.__aenter__()
        except BaseException:
            _deadline_var.reset(self._token)
            self._token = None
            raise
        return self._deadline_obj

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._timeout_ctx is not None:
                await self._timeout_ctx.__aexit__(exc_type, exc, tb)
        finally:
            if self._token is not None:
                _deadline_var.reset(self._token)
                self._token = None
