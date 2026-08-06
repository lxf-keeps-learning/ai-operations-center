"""Runtime 执行控制：注册、取消请求和清理。"""

import pytest

from app.runtime.execution_control import RuntimeExecutionRegistry


def test_request_cancel_marks_registered_session() -> None:
    registry = RuntimeExecutionRegistry()
    registry.register("session-1", "trace-1")

    assert registry.request_cancel("session-1") is True
    assert registry.is_cancel_requested("session-1") is True
    assert registry.trace_for_session("session-1") == "trace-1"


def test_cancel_unknown_session_returns_false() -> None:
    registry = RuntimeExecutionRegistry()

    assert registry.request_cancel("missing") is False


def test_unregister_removes_execution_handle() -> None:
    registry = RuntimeExecutionRegistry()
    registry.register("session-1", "trace-1")

    registry.unregister("session-1")

    assert registry.is_cancel_requested("session-1") is False
    assert registry.trace_for_session("session-1") is None
