"""Deadline 模块单元测试：绝对截止时间、子预算继承、统一超时异常。"""

import asyncio
import time

import pytest

from app.core.timeout import (
    Deadline,
    DeadlineExpiredError,
    current_deadline,
    deadline,
)


def test_deadline_uses_monotonic_clock() -> None:
    d = Deadline(10.0)
    assert d.remaining_seconds > 0
    assert d.remaining_seconds <= 10.0
    assert not d.expired


def test_deadline_countdown() -> None:
    d = Deadline(0.05)
    time.sleep(0.06)
    assert d.remaining_seconds <= 0.0
    assert d.expired


def test_child_timeout_caps_at_remaining_budget() -> None:
    d = Deadline(3.0)
    assert d.child_timeout(15.0) == pytest.approx(3.0, abs=0.5)
    d2 = Deadline(100.0)
    assert d2.child_timeout(15.0) == pytest.approx(15.0)


def test_child_deadline_from_parent() -> None:
    parent = Deadline(5.0)
    child = Deadline.from_parent(parent, 60.0)
    assert child.deadline_at <= parent.deadline_at + 1e-6
    assert child.remaining_seconds <= 5.0 + 1e-6


def test_deadline_expired_error_carries_context() -> None:
    err = DeadlineExpiredError(
        operation="report_generation",
        timeout_seconds=3.0,
        elapsed_ms=3100,
        remaining_ms=0,
        retryable=False,
        detail={"trace_id": "trace_1"},
    )
    assert err.operation == "report_generation"
    assert err.timeout_seconds == 3.0
    assert err.elapsed_ms == 3100
    assert err.retryable is False
    assert err.detail == {"trace_id": "trace_1"}


@pytest.mark.anyio
async def test_deadline_context_manager_propagates_budget() -> None:
    with pytest.raises(TimeoutError):
        async with deadline(0.05, operation="report"):
            while True:
                await asyncio.sleep(0.01)


@pytest.mark.anyio
async def test_nested_deadline_does_not_reset_budget() -> None:
    """报告只剩 3 秒时，子层不能重新获得完整 15 秒预算。"""
    async with deadline(3.0, operation="report"):
        d = current_deadline()
        assert d is not None
        assert d.child_timeout(15.0) <= 3.0 + 1e-6
        # 子层 deadline 也不会扩展父层预算
        async with deadline(15.0, operation="tool"):
            inner = current_deadline()
            assert inner is not None
            assert inner.remaining_seconds <= 3.0 + 1e-6


@pytest.mark.anyio
async def test_current_deadline_none_outside_context() -> None:
    assert current_deadline() is None


@pytest.mark.anyio
async def test_deadline_context_cleared_after_exit() -> None:
    async with deadline(5.0, operation="report"):
        assert current_deadline() is not None
    assert current_deadline() is None

