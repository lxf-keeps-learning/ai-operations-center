"""SseEventEmitter — 分析事件统一发送器。

Emitter 只负责创建标准事件和格式化 SSE，不包含业务判断逻辑。
"""

from app.analysis_stream.event_types import (
    EVENT_ANALYSIS_FAILED,
    EVENT_ANALYSIS_STARTED,
    EVENT_HEARTBEAT,
    EVENT_NODE_COMPLETED,
    EVENT_NODE_FAILED,
    EVENT_NODE_STARTED,
    EVENT_REPORT_COMPLETED,
    EVENT_STREAM_CLOSED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
)
from app.analysis_stream.schemas import AnalysisStreamEvent
from app.analysis_stream.sse_formatter import build_event, format_stream_event


class SseEventEmitter:
    """SSE 事件发射器。

    `create_*` 返回事件对象，适合先审计再发送；
    `emit_*` 保持旧调用习惯，直接返回 SSE 字符串。
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._sequence = 0

    @property
    def run_id(self) -> str:
        return self._run_id

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def format(self, event: AnalysisStreamEvent) -> str:
        return format_stream_event(event)

    def create_analysis_started(
        self,
        message: str = "分析任务已启动",
        payload: dict | None = None,
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_ANALYSIS_STARTED,
            status=STATUS_RUNNING,
            message=message,
            sequence=self._next_sequence(),
            payload=payload,
        )

    def emit_analysis_started(
        self,
        message: str = "分析任务已启动",
        payload: dict | None = None,
    ) -> str:
        """分析任务开始。"""
        return self.format(self.create_analysis_started(message, payload))

    def create_analysis_failed(
        self,
        message: str = "分析任务执行失败",
        error_code: str = "ANALYSIS_FAILED",
        error_message: str = "",
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_ANALYSIS_FAILED,
            status=STATUS_FAILED,
            message=message,
            sequence=self._next_sequence(),
            error_code=error_code,
            error_message=error_message,
        )

    def emit_analysis_failed(
        self,
        message: str = "分析任务执行失败",
        error_code: str = "ANALYSIS_FAILED",
        error_message: str = "",
    ) -> str:
        """整体分析失败。"""
        return self.format(self.create_analysis_failed(message, error_code, error_message))

    def create_report_completed(
        self,
        message: str = "分析报告已生成",
        payload: dict | None = None,
        duration_ms: int | None = None,
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_REPORT_COMPLETED,
            status=STATUS_COMPLETED,
            message=message,
            sequence=self._next_sequence(),
            duration_ms=duration_ms,
            payload=payload,
        )

    def emit_report_completed(
        self,
        message: str = "分析报告已生成",
        payload: dict | None = None,
        duration_ms: int | None = None,
    ) -> str:
        """报告生成完成。"""
        return self.format(self.create_report_completed(message, payload, duration_ms))

    def create_stream_closed(self, message: str = "事件流已关闭") -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_STREAM_CLOSED,
            status=STATUS_COMPLETED,
            message=message,
            sequence=self._next_sequence(),
        )

    def emit_stream_closed(self, message: str = "事件流已关闭") -> str:
        """流正常关闭。"""
        return self.format(self.create_stream_closed(message))

    def create_node_started(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        payload: dict | None = None,
        progress: int | None = None,
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_NODE_STARTED,
            status=STATUS_RUNNING,
            message=message or f"{node_name}开始执行",
            sequence=self._next_sequence(),
            node_key=node_key,
            node_name=node_name,
            payload=payload,
            progress=progress,
        )

    def emit_node_started(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        payload: dict | None = None,
        progress: int | None = None,
    ) -> str:
        """节点开始执行。"""
        return self.format(self.create_node_started(node_key, node_name, message, payload, progress))

    def create_node_completed(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        payload: dict | None = None,
        duration_ms: int | None = None,
        source_label: str | None = None,
        progress: int | None = None,
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_NODE_COMPLETED,
            status=STATUS_COMPLETED,
            message=message or f"{node_name}执行完成",
            sequence=self._next_sequence(),
            node_key=node_key,
            node_name=node_name,
            duration_ms=duration_ms,
            source_label=source_label,
            payload=payload,
            progress=progress,
        )

    def emit_node_completed(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        payload: dict | None = None,
        duration_ms: int | None = None,
        source_label: str | None = None,
        progress: int | None = None,
    ) -> str:
        """节点执行完成。"""
        return self.format(
            self.create_node_completed(
                node_key,
                node_name,
                message,
                payload,
                duration_ms,
                source_label,
                progress,
            )
        )

    def create_node_failed(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        error_code: str = "NODE_FAILED",
        error_message: str = "",
        duration_ms: int | None = None,
    ) -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_NODE_FAILED,
            status=STATUS_FAILED,
            message=message or f"{node_name}执行失败",
            sequence=self._next_sequence(),
            node_key=node_key,
            node_name=node_name,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
        )

    def emit_node_failed(
        self,
        node_key: str,
        node_name: str,
        message: str = "",
        error_code: str = "NODE_FAILED",
        error_message: str = "",
        duration_ms: int | None = None,
    ) -> str:
        """节点执行失败。"""
        return self.format(
            self.create_node_failed(
                node_key,
                node_name,
                message,
                error_code,
                error_message,
                duration_ms,
            )
        )

    def create_heartbeat(self, message: str = "heartbeat") -> AnalysisStreamEvent:
        return build_event(
            run_id=self._run_id,
            event_type=EVENT_HEARTBEAT,
            status=STATUS_RUNNING,
            message=message,
            sequence=self._next_sequence(),
        )

    def emit_heartbeat(self, message: str = "heartbeat") -> str:
        """心跳事件。"""
        return self.format(self.create_heartbeat(message))
