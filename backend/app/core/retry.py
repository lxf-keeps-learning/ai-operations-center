"""异步重试基础设施 — 供 Operation Agent 的 Tool 与 LLM 调用复用。

设计要点：
  - 最大尝试次数 max_attempts（默认 2 = 初次调用 + 一次重试）。
  - 退避时间：min(initial_backoff * 2^(attempt-1), max_backoff)。
  - 支持可注入的确定性 jitter；测试将 jitter 置 0 即可固定。
  - 每次重试前检查绝对 Deadline：剩余预算少于 min_recovery_budget_seconds
    时不 sleep、不发起下一次调用。
  - asyncio.CancelledError 原样向上传播，不包装。
  - 不引入 tenacity 等第三方依赖。

事件钩子：
  on_event(event_type, fields) 会收到 retry_started / retry_scheduled /
  retry_succeeded / retry_exhausted，供观测与恢复事件记录使用。
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.core.timeout import Deadline

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略参数（从 Settings 映射，便于测试注入）。"""

    max_attempts: int = 2
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 2.0
    min_recovery_budget_seconds: float = 15.0
    jitter: float = 0.0


@dataclass
class RetryOutcome(Generic[T]):
    """一次重试流程的最终结果。"""

    result: T
    attempts: int = 1
    retried: bool = False
    exhausted: bool = False
    duration_ms: int = 0
    reason: str | None = None


RetryEventHook = Callable[[str, dict[str, Any]], None]
RetryAttempt = Callable[[], Awaitable[T]]
RetryPredicate = Callable[[T], bool]
RetryDelayResolver = Callable[[T], float | None]


def compute_backoff_seconds(policy: RetryPolicy, attempt: int) -> float:
    """退避时间：min(initial * 2^(attempt-1), max)。attempt 从 1 开始。"""
    raw = policy.initial_backoff_seconds * (2 ** (attempt - 1))
    return min(raw, policy.max_backoff_seconds)


def apply_jitter(backoff: float, policy: RetryPolicy, rng: random.Random) -> float:
    """按 policy.jitter 比例注入 jitter；jitter=0 时完全确定。"""
    if policy.jitter <= 0 or backoff <= 0:
        return backoff
    spread = backoff * min(policy.jitter, 1.0)
    return max(0.0, backoff + rng.uniform(-spread, spread))


async def run_with_retry(
    attempt: RetryAttempt[T],
    *,
    should_retry: RetryPredicate[T],
    is_success: RetryPredicate[T],
    policy: RetryPolicy,
    deadline: Deadline | None = None,
    on_event: RetryEventHook | None = None,
    operation: str = "operation",
    rng: random.Random | None = None,
    retry_delay_seconds: RetryDelayResolver[T] | None = None,
) -> RetryOutcome[T]:
    """按策略执行 attempt，并对 should_retry 判定为可重试的结果重试。

    返回最后一次结果（无论成功或已耗尽重试次数）。调用方根据
    outcome.exhausted 决定是否进入降级路径。
    """
    rng = rng or random.Random()
    start = time.monotonic()
    attempts = 0

    while True:
        attempts += 1
        _notify(on_event, "retry_started", {
            "operation": operation,
            "attempt": attempts,
            "recovery_cycle": None,
        })
        result = await attempt()

        retryable = should_retry(result)
        if not retryable:
            if is_success(result):
                _notify(on_event, "retry_succeeded", {
                    "operation": operation,
                    "attempt": attempts,
                    "recovery_cycle": None,
                })
            return RetryOutcome(
                result=result,
                attempts=attempts,
                retried=attempts > 1,
                exhausted=False,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if attempts >= policy.max_attempts:
            _notify(on_event, "retry_exhausted", {
                "operation": operation,
                "attempt": attempts,
                "recovery_cycle": None,
                "reason": "max_attempts_reached",
            })
            return RetryOutcome(
                result=result,
                attempts=attempts,
                retried=attempts > 1,
                exhausted=True,
                duration_ms=int((time.monotonic() - start) * 1000),
                reason="max_attempts_reached",
            )

        backoff = compute_backoff_seconds(policy, attempts)
        if retry_delay_seconds is not None:
            requested_delay = retry_delay_seconds(result)
            if requested_delay is not None:
                backoff = min(max(0.0, requested_delay), policy.max_backoff_seconds)
        backoff = apply_jitter(backoff, policy, rng)
        remaining = _remaining_budget(deadline)
        if (
            remaining is not None
            and remaining - backoff < policy.min_recovery_budget_seconds
        ):
            _notify(on_event, "retry_exhausted", {
                "operation": operation,
                "attempt": attempts,
                "recovery_cycle": None,
                "reason": "deadline_budget",
                "remaining_seconds": round(remaining, 3),
            })
            return RetryOutcome(
                result=result,
                attempts=attempts,
                retried=True,
                exhausted=True,
                duration_ms=int((time.monotonic() - start) * 1000),
                reason="deadline_budget",
            )

        _notify(on_event, "retry_scheduled", {
            "operation": operation,
            "attempt": attempts,
            "recovery_cycle": None,
            "backoff_seconds": round(backoff, 3),
        })
        await asyncio.sleep(backoff)


def _remaining_budget(deadline: Deadline | None) -> float | None:
    if deadline is None:
        return None
    return deadline.remaining_seconds


def _notify(hook: RetryEventHook | None, event_type: str, fields: dict[str, Any]) -> None:
    if hook is not None:
        try:
            hook(event_type, fields)
        except Exception:  # noqa: BLE001 - 观测钩子失败不得影响业务
            pass
