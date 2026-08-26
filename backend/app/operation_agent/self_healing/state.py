"""OperationState 自修复字段的统一读写与状态计算。"""

from __future__ import annotations

from typing import Any

from app.operation_agent.self_healing.constants import (
    SH_DEGRADED,
    SH_EXHAUSTED,
    SH_NOT_RUN,
    SH_RECOVERED,
    default_self_healing,
)
from app.operation_agent.state import OperationState


def get_self_healing(state: OperationState) -> dict[str, Any]:
    """读取并初始化 self_healing；缺失时返回默认 not_run 结构。"""
    sh = state.get("self_healing")
    if not isinstance(sh, dict):
        sh = default_self_healing()
        state["self_healing"] = sh
    for key, value in default_self_healing().items():
        sh.setdefault(key, value)
    return sh


def init_recovery_state(state: OperationState) -> OperationState:
    """确保自修复相关容器字段存在（幂等）。"""
    get_self_healing(state)
    state.setdefault("recovery_context", {})
    state.setdefault("evaluation_results", [])
    state.setdefault("recovery_events", [])
    return state


def compute_api_status(state: OperationState) -> str:
    """统一状态计算：同步 API、Service、SSE 共用。

    规则：
      - recovered 且无未解决错误 → success
      - degraded / exhausted 且有最终报告 → partial
      - 没有最终报告 → failed
      - 其余（not_run / passed）沿用旧逻辑：有报告且无 errors → success。
    """
    final_answer = state.get("final_answer")
    errors = state.get("errors", [])
    if not final_answer:
        return "failed"

    sh = state.get("self_healing") or {}
    sh_status = sh.get("status")

    if sh_status == SH_RECOVERED:
        return "success" if not errors else "partial"
    if sh_status in {SH_DEGRADED, SH_EXHAUSTED}:
        return "partial"
    if errors:
        return "partial"
    return "success"


def self_healing_from_record(record: Any) -> dict[str, Any]:
    """从旧缓存记录读取 self_healing；无自修复数据时返回 not_run。"""
    raw = getattr(record, "self_healing_json", None)
    if isinstance(raw, dict) and raw.get("status"):
        sh = default_self_healing()
        sh.update(raw)
        return sh
    sh = default_self_healing()
    sh["status"] = SH_NOT_RUN
    return sh
