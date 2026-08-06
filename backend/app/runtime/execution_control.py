"""进程内 Runtime 执行控制。

当前服务以单进程为主，使用事件让 Session API 向正在运行的 Graph 发出
协作式取消请求。后续多 Worker 部署时可将该接口替换为 Redis 实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock


class RuntimeCancelledError(Exception):
    """Runtime 执行收到取消请求后抛出的内部控制异常。"""


@dataclass
class ExecutionHandle:
    session_id: str
    trace_id: str
    cancel_event: Event = field(default_factory=Event)


class RuntimeExecutionRegistry:
    def __init__(self) -> None:
        self._handles: dict[str, ExecutionHandle] = {}
        self._lock = Lock()

    def register(self, session_id: str, trace_id: str) -> ExecutionHandle:
        handle = ExecutionHandle(session_id=session_id, trace_id=trace_id)
        with self._lock:
            self._handles[session_id] = handle
        return handle

    def unregister(self, session_id: str) -> None:
        with self._lock:
            self._handles.pop(session_id, None)

    def request_cancel(self, session_id: str) -> bool:
        with self._lock:
            handle = self._handles.get(session_id)
        if handle is None:
            return False
        handle.cancel_event.set()
        return True

    def is_cancel_requested(self, session_id: str) -> bool:
        with self._lock:
            handle = self._handles.get(session_id)
        return bool(handle and handle.cancel_event.is_set())

    def trace_for_session(self, session_id: str) -> str | None:
        with self._lock:
            handle = self._handles.get(session_id)
        return handle.trace_id if handle else None

    def session_for_trace(self, trace_id: str) -> str | None:
        with self._lock:
            for handle in self._handles.values():
                if handle.trace_id == trace_id:
                    return handle.session_id
        return None


runtime_execution_registry = RuntimeExecutionRegistry()


def raise_if_cancelled(session_id: str) -> None:
    if runtime_execution_registry.is_cancel_requested(session_id):
        raise RuntimeCancelledError(f"Session {session_id} 已请求取消")
