import logging
from time import perf_counter
from typing import Any

from app.utils.ids import new_trace_id

logger = logging.getLogger("ioc.tool_trace")

_SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization", "credential"}


class ToolTraceRecord:
    def __init__(self) -> None:
        self.trace_id: str = ""
        self.tool_name: str = ""
        self.input_summary: dict[str, Any] = {}
        self.success: bool = False
        self.error_code: str | None = None
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_ms: int = 0
        self.evidence_count: int = 0


def start_trace(tool_name: str, input_data: dict | None = None) -> tuple[str, float]:
    trace_id = new_trace_id()
    start = perf_counter()
    logger.info(
        "TOOL_START  trace_id=%s tool=%s input=%s",
        trace_id,
        tool_name,
        _sanitize_for_trace(input_data or {}),
    )
    return trace_id, start


def end_trace(
    trace_id: str,
    tool_name: str,
    start_time: float,
    success: bool,
    error_code: str | None = None,
    evidence_count: int = 0,
    input_summary: dict | None = None,
    metadata: dict | None = None,
) -> None:
    duration_ms = max(1, int((perf_counter() - start_time) * 1000))
    record_tool_trace(
        trace_id,
        tool_name,
        input_summary=input_summary,
        success=success,
        error_code=error_code,
        duration_ms=duration_ms,
        evidence_count=evidence_count,
        metadata=metadata,
    )


def record_tool_trace(
    trace_id: str,
    tool_name: str,
    input_summary: dict | None,
    success: bool,
    error_code: str | None,
    duration_ms: int,
    evidence_count: int = 0,
    metadata: dict | None = None,
) -> None:
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        "TOOL_%s trace_id=%s tool=%s duration_ms=%d error=%s evidence=%d input=%s metadata=%s",
        status,
        trace_id,
        tool_name,
        duration_ms,
        error_code or "-",
        evidence_count,
        _sanitize_for_trace(input_summary or {}),
        _sanitize_for_trace(metadata or {}),
    )


def _sanitize_for_trace(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_key(key) else _sanitize_for_trace(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_for_trace(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > 200:
        return f"{value[:200]}..."
    return value


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(sensitive in normalized for sensitive in _SENSITIVE_KEYS)
