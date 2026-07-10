"""SSE 事件格式化工具。"""

from uuid import uuid4

from app.analysis_stream.schemas import AnalysisStreamEvent
from app.utils.sse import to_sse
from app.utils.timezone import now_local


def _now_iso() -> str:
    return now_local().isoformat()


def _new_event_id() -> str:
    return uuid4().hex[:16]


def build_event(
    run_id: str,
    event_type: str,
    status: str,
    message: str,
    *,
    sequence: int | None = None,
    node_key: str | None = None,
    node_name: str | None = None,
    duration_ms: int | None = None,
    source_label: str | None = None,
    payload: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    progress: int | None = None,
) -> AnalysisStreamEvent:
    """生成同源事件对象，供 SSE 输出、内存日志和审计表复用。"""
    event: AnalysisStreamEvent = {
        "run_id": run_id,
        "event_id": _new_event_id(),
        "sequence": sequence or 0,
        "event_type": event_type,
        "status": status,
        "message": message,
        "timestamp": _now_iso(),
    }

    if node_key is not None:
        event["node_key"] = node_key
    if node_name is not None:
        event["node_name"] = node_name
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    if source_label is not None:
        event["source_label"] = source_label
    if payload is not None:
        event["payload"] = payload
    if error_code is not None:
        event["error_code"] = error_code
    if error_message is not None:
        event["error_message"] = error_message
    if progress is not None:
        event["progress"] = progress

    return event


def format_stream_event(event: AnalysisStreamEvent) -> str:
    """将已构造事件原样格式化为 SSE 字符串。"""
    return to_sse(str(event["event_type"]), {k: v for k, v in event.items() if v is not None})


def format_event(
    run_id: str,
    event_type: str,
    status: str,
    message: str,
    *,
    sequence: int | None = None,
    node_key: str | None = None,
    node_name: str | None = None,
    duration_ms: int | None = None,
    source_label: str | None = None,
    payload: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    progress: int | None = None,
) -> str:
    """生成标准 SSE 事件字符串：event + data + 空行。"""
    return format_stream_event(
        build_event(
            run_id=run_id,
            event_type=event_type,
            status=status,
            message=message,
            sequence=sequence,
            node_key=node_key,
            node_name=node_name,
            duration_ms=duration_ms,
            source_label=source_label,
            payload=payload,
            error_code=error_code,
            error_message=error_message,
            progress=progress,
        )
    )
