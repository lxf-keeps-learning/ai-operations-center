"""Tool 调用重试策略（Operation Agent 专用）。

规则：
  - 仅查询类、分析类 Tool 可以重试（action Tool 永不重试）。
  - 只有 ToolError.retryable=true 才允许重试。
  - WRITE_RESULT_UNKNOWN 永不重试。
  - 参数错误、权限错误、确认挑战、内容安全错误永不重试。
  - TOOL_RATE_LIMITED 仅在 retry_after_seconds <= 2 时重试（Deadline 预算由
    run_with_retry 的 min_recovery_budget 保护）。
  - 成功的 Tool 不得因为其他 Tool 失败而重复调用（本模块只对单次失败结果判定）。
"""

from __future__ import annotations

from typing import Any

from app.tool_center.contracts import ToolResult

# Operation Graph 允许重试的 Tool 能力（全部为查询/分析类）。
RETRYABLE_TOOL_CAPABILITIES: frozenset[str] = frozenset({
    "query.kpi",
    "query.alarm",
    "query.risk",
    "query.work_order",
    "analysis.ioc_summary",
})

# 永不重试的错误码：参数、权限、确认挑战、内容安全、写入结果未知、配置错误。
_NEVER_RETRY_CODES: frozenset[str] = frozenset({
    "WRITE_RESULT_UNKNOWN",
    "TOOL_VALIDATION_ERROR",
    "TOOL_FORBIDDEN",
    "TOOL_CONFIRMATION_REQUIRED",
    "TOOL_CAPABILITY_UNAVAILABLE",
    "TOOL_NOT_FOUND",
    "TOOL_REGISTRY_CONFIGURATION_ERROR",
    "CONTENT_SAFETY_BLOCKED",
})


def tool_is_retryable(capability: str) -> bool:
    return capability in RETRYABLE_TOOL_CAPABILITIES


def should_retry_tool_result(result: ToolResult | None, capability: str) -> bool:
    """单个 ToolResult 是否可重试（不涉及成功 Tool 的重复调用）。"""
    if not tool_is_retryable(capability):
        return False
    if result is None or result.success:
        return False
    error = result.error
    if error is None:
        return False
    code = error.code or ""
    if code in _NEVER_RETRY_CODES:
        return False
    if code == "TOOL_RATE_LIMITED":
        retry_after = _retry_after_seconds(error.detail)
        return retry_after is not None and retry_after <= 2
    return bool(error.retryable)


def get_tool_retry_delay_seconds(result: ToolResult | None) -> float | None:
    """返回受策略上限保护的 Tool Retry-After；非限流结果使用默认退避。"""
    if result is None or result.error is None or result.error.code != "TOOL_RATE_LIMITED":
        return None
    retry_after = _retry_after_seconds(result.error.detail)
    if retry_after is None or retry_after > 2:
        return None
    return max(0.0, retry_after)


def _retry_after_seconds(detail: dict[str, Any] | None) -> float | None:
    if not isinstance(detail, dict):
        return None
    raw = detail.get("retry_after_seconds")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
