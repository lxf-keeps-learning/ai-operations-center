"""Operation 自修复可观测事件记录。

同步目标：
  - 结构化日志（脱敏，不含完整用户输入 / Prompt / API Key / CoT）；
  - OperationState.recovery_events（随报告持久化）；
  - LangGraph custom 流事件（LangSmith trace / SSE 展示可消费）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.config import get_stream_writer

from app.operation_agent.state import OperationState

logger = logging.getLogger(__name__)


def emit_recovery_event(
    state: OperationState,
    event_type: str,
    *,
    node: str | None = None,
    operation: str | None = None,
    attempt: int | None = None,
    recovery_cycle: int | None = None,
    error_code: str | None = None,
    score: float | None = None,
    replan_target: str | None = None,
    duration_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """记录一条脱敏恢复事件到日志、recovery_events 与 custom 流事件。

    不记录完整用户输入、完整 Prompt、API Key 或 Chain-of-Thought。
    """
    trace_id = state.get("trace_id") or ""
    event: dict[str, Any] = {
        "event_type": event_type,
        "trace_id": trace_id,
        "timestamp": time.time(),
        "duration_ms": duration_ms,
    }
    if node:
        event["node"] = node
    if operation:
        event["operation"] = operation
    if attempt is not None:
        event["attempt"] = attempt
    if recovery_cycle is not None:
        event["recovery_cycle"] = recovery_cycle
    if error_code:
        event["error_code"] = error_code
    if score is not None:
        event["score"] = score
    if replan_target:
        event["replan_target"] = replan_target
    if extra:
        event.update(extra)

    try:
        state.setdefault("recovery_events", []).append(event)
    except Exception:  # noqa: BLE001 - 状态记录失败不影响主流程
        pass

    logger.info(
        "self_healing_event event_type=%s trace_id=%s node=%s operation=%s "
        "attempt=%s cycle=%s error_code=%s score=%s replan_target=%s duration_ms=%s",
        event_type,
        trace_id,
        node or "-",
        operation or "-",
        attempt,
        recovery_cycle,
        error_code or "-",
        score,
        replan_target or "-",
        duration_ms,
    )

    try:
        writer = get_stream_writer()
        writer({"kind": "operation_event", **event})
    except RuntimeError:
        pass


def record_operation_attempts(
    state: OperationState,
    operation: str,
    *,
    attempts: int,
    exhausted: bool,
    error_code: str | None = None,
) -> None:
    """累计全部实际尝试，仅把真正重试或提前耗尽的操作列为重试项。"""
    from app.operation_agent.self_healing.state import get_self_healing

    sh = get_self_healing(state)
    sh["total_attempts"] = sh.get("total_attempts", 0) + attempts
    if attempts > 1 or exhausted:
        sh["retried_operations"].append({
            "operation": operation,
            "attempts": attempts,
            "exhausted": exhausted,
            "error_code": error_code,
        })


def record_retried_operation(
    state: OperationState,
    operation: str,
    *,
    attempts: int,
    exhausted: bool,
    error_code: str | None = None,
) -> None:
    """兼容旧调用名；新代码使用 record_operation_attempts。"""
    record_operation_attempts(
        state,
        operation,
        attempts=attempts,
        exhausted=exhausted,
        error_code=error_code,
    )
