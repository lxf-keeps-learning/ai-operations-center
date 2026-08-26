"""核心异步重试模块测试。

覆盖：
  1. 退避时间计算与上限。
  2. jitter=0 时完全确定。
  3. 最大尝试次数 = 2（初次 + 一次重试）。
  4. Deadline 剩余预算不足时，不 sleep、不重试。
  5. asyncio.CancelledError 原样穿透。
  6. 事件钩子序列。
"""

import asyncio
import random
from types import SimpleNamespace

import pytest

from app.core.retry import (
    RetryOutcome,
    RetryPolicy,
    apply_jitter,
    compute_backoff_seconds,
    run_with_retry,
)
from app.core.timeout import Deadline


def _fake_deadline(remaining_seconds: float) -> Deadline:
    """构造一个剩余预算可控的 Deadline（基于自定义单调时钟）。"""
    start = 1000.0
    clock = SimpleNamespace(return_value=start)

    def fake_clock() -> float:
        return clock.return_value

    deadline = Deadline(remaining_seconds, clock=fake_clock)
    # deadline_at = start + remaining_seconds；clock 停在 start 时剩余正好 remaining
    return deadline


def test_compute_backoff_seconds_caps_at_max() -> None:
    policy = RetryPolicy(initial_backoff_seconds=0.5, max_backoff_seconds=2.0)
    assert compute_backoff_seconds(policy, 1) == pytest.approx(0.5)
    assert compute_backoff_seconds(policy, 2) == pytest.approx(1.0)
    assert compute_backoff_seconds(policy, 3) == pytest.approx(2.0)
    assert compute_backoff_seconds(policy, 4) == pytest.approx(2.0)


def test_apply_jitter_is_deterministic_when_zero() -> None:
    policy = RetryPolicy(jitter=0.0)
    assert apply_jitter(1.0, policy, random.Random(42)) == 1.0


def test_apply_jitter_injects_controlled_spread() -> None:
    policy = RetryPolicy(jitter=0.2)
    values = {apply_jitter(1.0, policy, random.Random(seed)) for seed in range(20)}
    assert all(0.8 <= value <= 1.2 for value in values)
    assert len(values) > 1


@pytest.mark.anyio
async def test_first_attempt_success_no_retry() -> None:
    calls = []

    async def attempt() -> str:
        calls.append(1)
        return "ok"

    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(),
    )
    assert outcome.result == "ok"
    assert outcome.attempts == 1
    assert outcome.retried is False
    assert outcome.exhausted is False
    assert calls == [1]


@pytest.mark.anyio
async def test_second_attempt_succeeds_after_first_failure() -> None:
    calls = []

    async def attempt() -> str:
        calls.append(1)
        return "fail" if len(calls) == 1 else "ok"

    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(),
        rng=random.Random(0),
    )
    assert outcome.result == "ok"
    assert outcome.attempts == 2
    assert outcome.retried is True
    assert outcome.exhausted is False
    assert calls == [1, 1]


@pytest.mark.anyio
async def test_max_attempts_two_exhausts_after_two_calls() -> None:
    calls = []

    async def attempt() -> str:
        calls.append(1)
        return "fail"

    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(max_attempts=2),
        rng=random.Random(0),
    )
    assert outcome.exhausted is True
    assert outcome.attempts == 2
    assert calls == [1, 1]


@pytest.mark.anyio
async def test_deadline_budget_insufficient_skips_sleep_and_retry() -> None:
    calls = []
    slept = []

    async def attempt() -> str:
        calls.append(1)
        return "fail"

    async def fake_sleep(_seconds: float) -> None:
        slept.append(_seconds)

    policy = RetryPolicy(min_recovery_budget_seconds=15.0)
    deadline = _fake_deadline(remaining_seconds=5.0)

    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=policy,
        deadline=deadline,
    )
    assert outcome.exhausted is True
    assert outcome.reason == "deadline_budget"
    assert outcome.attempts == 1
    assert calls == [1]
    assert slept == []


@pytest.mark.anyio
async def test_cancelled_error_propagates() -> None:
    async def attempt() -> str:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_with_retry(
            attempt,
            should_retry=lambda result: True,
            is_success=lambda _result: False,
            policy=RetryPolicy(max_attempts=3),
        )


@pytest.mark.anyio
async def test_event_hook_sequence() -> None:
    events: list[tuple[str, dict]] = []
    calls = []

    async def attempt() -> str:
        calls.append(1)
        return "fail" if len(calls) == 1 else "ok"

    await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(max_attempts=3),
        on_event=lambda event_type, fields: events.append((event_type, fields)),
        operation="llm:test",
        rng=random.Random(0),
    )

    types = [event_type for event_type, _ in events]
    assert types == ["retry_started", "retry_scheduled", "retry_started", "retry_succeeded"]
    assert events[0][1]["operation"] == "llm:test"
    assert events[0][1]["attempt"] == 1
    assert events[1][1]["backoff_seconds"] == pytest.approx(0.5)


@pytest.mark.anyio
async def test_non_retryable_failure_does_not_emit_retry_succeeded() -> None:
    events: list[str] = []

    async def attempt() -> str:
        return "invalid_request"

    outcome = await run_with_retry(
        attempt,
        should_retry=lambda _result: False,
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(),
        on_event=lambda event_type, _fields: events.append(event_type),
    )

    assert outcome.result == "invalid_request"
    assert outcome.exhausted is False
    assert events == ["retry_started"]


@pytest.mark.anyio
async def test_deadline_reserves_budget_after_backoff(monkeypatch) -> None:
    calls: list[int] = []
    slept: list[float] = []

    async def attempt() -> str:
        calls.append(1)
        return "fail"

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("app.core.retry.asyncio.sleep", fake_sleep)
    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: result == "fail",
        is_success=lambda result: result == "ok",
        policy=RetryPolicy(
            initial_backoff_seconds=0.5,
            min_recovery_budget_seconds=15.0,
        ),
        deadline=_fake_deadline(remaining_seconds=15.4),
    )

    assert outcome.reason == "deadline_budget"
    assert calls == [1]
    assert slept == []


@pytest.mark.anyio
async def test_retry_delay_override_controls_sleep(monkeypatch) -> None:
    calls: list[int] = []
    slept: list[float] = []

    async def attempt() -> dict:
        calls.append(1)
        return {"success": len(calls) > 1, "retry_after": 1.5}

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("app.core.retry.asyncio.sleep", fake_sleep)
    outcome = await run_with_retry(
        attempt,
        should_retry=lambda result: not result["success"],
        is_success=lambda result: result["success"],
        retry_delay_seconds=lambda result: result.get("retry_after"),
        policy=RetryPolicy(max_backoff_seconds=2.0),
    )

    assert outcome.result["success"] is True
    assert slept == [1.5]
