# 工具遥测模块
#
# 提供 Tool 执行的日志记录、敏感数据脱敏等观测能力。
# 不维护独立的 Trace 上下文，统一复用 app/core/trace。
# trace_id 来自全局请求上下文，tool_call_id 在此处生成用于工具级标识。

import hashlib
import json
from typing import Any

from app.core.logging.logger import get_logger

logger = get_logger("ioc.tool_trace")

# 需要脱敏的敏感字段 key 集合，命中后日志输出 ***
_SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization", "credential"}


def sanitize_for_trace(value: Any) -> Any:
    """递归脱敏：字典中敏感 key 替换为 ***，列表截断前 20 项，长字符串截断 200 字符。"""
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_key(key) else sanitize_for_trace(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [sanitize_for_trace(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > 200:
        return f"{value[:200]}..."
    return value


def _is_sensitive_key(key: Any) -> bool:
    """判断 key 是否包含敏感字段名称（不区分大小写）。"""
    normalized = str(key).lower()
    return any(sensitive in normalized for sensitive in _SENSITIVE_KEYS)


def hash_arguments(arguments: dict[str, Any]) -> str:
    """参数规范化哈希：字典按 key 排序后做紧凑 JSON 序列化，再做 SHA-256。

    用于审计 argument_hash 与动作确认凭证的参数防篡改绑定。
    """
    canonical = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_argument_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    """构建审计用的递归脱敏参数摘要，不保存原始敏感值。"""
    return sanitize_for_trace(arguments)


def record_tool_trace(
    *,
    trace_id: str,
    tool_name: str,
    duration_ms: int,
    success: bool,
    error_code: str | None = None,
    evidence_count: int = 0,
    input_summary: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """写入一条 Tool 执行记录日志，包含状态、耗时、证据数量和入参元信息。"""
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        "TOOL_%s trace_id=%s tool=%s duration_ms=%d error=%s evidence=%d input=%s metadata=%s",
        status,
        trace_id,
        tool_name,
        duration_ms,
        error_code or "-",
        evidence_count,
        sanitize_for_trace(input_summary or {}),
        sanitize_for_trace(metadata or {}),
    )
