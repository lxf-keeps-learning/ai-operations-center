"""SSE Streaming 事件数据结构。"""

from typing import Any, NotRequired, TypedDict


class AnalysisStreamEvent(TypedDict, total=False):
    """统一的 SSE 分析事件结构。

    source_label — 数据来源标签，如 "Mock IOC · 23ms"、"DeepSeek · 1.2s"
    """

    run_id: str
    event_id: str
    sequence: int
    event_type: str
    node_key: NotRequired[str]
    node_name: NotRequired[str]
    status: str
    message: str
    duration_ms: NotRequired[int]
    source_label: NotRequired[str]
    progress: NotRequired[int]
    payload: NotRequired[dict[str, Any]]
    error_code: NotRequired[str]
    error_message: NotRequired[str]
    timestamp: str
