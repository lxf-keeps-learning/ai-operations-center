"""
LangGraph Stream Event Adapter — 将 LangGraph 运行时 StreamPart 转换为 AnalysisStreamEvent。

职责边界：
- 只做事件格式转换，不做业务判断。
- 不感知 HTTP、SSE 协议、前端协议。
- 产生的 AnalysisStreamEvent 供 stream_service 进一步处理。

映射规则：
  LangGraph 来源               业务事件
  ──────────────────────────  ─────────────────
  custom.kind=node_started    node_started
  custom.kind=report_delta    report_delta
  updates 中节点更新            node_completed
  未知 custom 事件              安全忽略

LangGraph astream 输出格式（LangGraph 1.2.9）：
  ('updates', {node_key: state_update})
  ('custom', {custom_data})
  ('values', {full_state})
"""
import time
from typing import Any

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.schemas import AnalysisStreamEvent
from app.operation_agent.state import OperationState


def _calc_progress(
    node_key: str,
    status: str,
    node_order: list[str],
) -> int | None:
    """根据节点在 Graph 中的位置计算进度百分比。"""
    if not node_order:
        return None
    try:
        idx = node_order.index(node_key)
    except ValueError:
        return None
    total = len(node_order)
    if status == "started":
        return int(idx * 100 / total)
    return int((idx + 1) * 100 / total)


def _detect_source_label(
    state_update: dict[str, Any],
    node_key: str,
    duration_ms: int,
) -> str:
    """根据节点类型和 State 增量识别数据来源标签。"""
    formatted_ms = (
        f"{duration_ms}ms" if duration_ms < 1000
        else f"{duration_ms / 1000:.1f}s"
    )
    node_source_map = {
        "init_context": f"本地初始化 · {formatted_ms}",
        "query_operation_data": _data_source_label(state_update, formatted_ms),
        "detect_abnormal": f"规则引擎 · {formatted_ms}",
        "analyze_reason": _llm_source_label(state_update, formatted_ms),
        "generate_advice": _llm_source_label(state_update, formatted_ms),
        "summary": f"Markdown 渲染 · {formatted_ms}",
    }
    return node_source_map.get(node_key, f"Node · {formatted_ms}")


def _data_source_label(state: dict[str, Any], formatted: str) -> str:
    raw = state.get("raw_data", {})
    if not raw:
        return f"Mock IOC · {formatted}"
    snapshot = raw.get("domain_snapshot")
    ioc = raw.get("ioc_summary")
    if snapshot:
        return f"Mock IOC · {formatted}"
    if ioc:
        return f"Tool Center · {formatted}"
    kpi = raw.get("kpi_items", [])
    alarms = raw.get("alarm_items", [])
    if kpi or alarms:
        return f"Tool Center · {formatted}"
    return f"Mock IOC · {formatted}"


def _llm_source_label(state: dict[str, Any], formatted: str) -> str:
    usages = state.get("llm_usages", [])
    last_usage = usages[-1] if usages else {}
    model = (
        last_usage.get("model_name", "deepseek-chat")
        if last_usage.get("success")
        else "deepseek-chat"
    )
    model_str = str(model).lower()
    if "deepseek" in model_str:
        return f"DeepSeek · {formatted}"
    if "qwen" in model_str:
        return f"Qwen · {formatted}"
    if "doubao" in model_str:
        return f"Doubao · {formatted}"
    return f"LLM · {formatted}"


class LangGraphEventAdapter:
    """将 LangGraph astream 输出转换为 AnalysisStreamEvent。

    使用方式：
        adapter = LangGraphEventAdapter(emitter, node_order)
        async for mode, data in graph.astream(input, stream_mode=[...]):
            for event in adapter.process(mode, data):
                yield event
        for event in adapter.flush():
            yield event
        final_state = adapter.get_final_state()
    """

    def __init__(
        self,
        emitter: SseEventEmitter,
        node_metadata: dict[str, dict[str, str]],
        node_order: list[str],
    ) -> None:
        self._emitter = emitter
        self._node_metadata = node_metadata
        self._node_order = node_order
        self._node_start_times: dict[str, float] = {}
        self._latest_full_state: OperationState | None = None
        self._started_nodes: set[str] = set()
        self._completed_nodes: set[str] = set()

    def process(
        self,
        mode: str,
        data: Any,
    ) -> list[AnalysisStreamEvent]:
        """处理一条 LangGraph 流事件，返回 0-N 个业务事件。"""
        if mode == "values":
            return self._process_values(data)
        elif mode == "custom":
            return self._process_custom(data)
        elif mode == "updates":
            return self._process_updates(data)
        return []

    def _process_values(self, data: Any) -> list[AnalysisStreamEvent]:
        if isinstance(data, dict):
            self._latest_full_state = data
        return []

    def _process_custom(self, data: Any) -> list[AnalysisStreamEvent]:
        if not isinstance(data, dict):
            return []
        kind = data.get("kind")
        if kind == "report_delta":
            delta = data.get("delta", "")
            if not isinstance(delta, str) or not delta:
                return []
            return [self._emitter.create_report_delta(delta)]
        if kind != "node_started":
            return []
        node_key = data.get("node_key", "")
        if (
            not node_key
            or node_key not in self._node_metadata
            or node_key in self._started_nodes
            or node_key in self._completed_nodes
        ):
            return []
        self._started_nodes.add(node_key)
        self._node_start_times[node_key] = time.monotonic()
        meta = self._node_metadata.get(node_key, {})
        event = self._emitter.create_node_started(
            node_key=node_key,
            node_name=meta.get("name", node_key),
            message=meta.get("message_started", f"{node_key} 执行中"),
            progress=_calc_progress(node_key, "started", self._node_order),
        )
        return [event]

    def _process_updates(self, data: Any) -> list[AnalysisStreamEvent]:
        if not isinstance(data, dict):
            return []
        events: list[AnalysisStreamEvent] = []
        for node_key, state_update in data.items():
            # LangGraph 可能输出 interrupt 等内部 update；对外协议只暴露
            # Operation Graph 注册过的真实业务节点，并保证 completed 幂等。
            if (
                node_key not in self._node_metadata
                or node_key in self._completed_nodes
            ):
                continue
            start_time = self._node_start_times.pop(node_key, None)
            duration_ms = (
                int((time.monotonic() - start_time) * 1000)
                if start_time
                else 0
            )
            meta = self._node_metadata.get(node_key, {})

            safe_update = state_update if isinstance(state_update, dict) else {}
            source_label = _detect_source_label(safe_update, node_key, duration_ms)

            event = self._emitter.create_node_completed(
                node_key=node_key,
                node_name=meta.get("name", node_key),
                message=meta.get(
                    "message_completed", f"{node_key} 执行完成",
                ),
                duration_ms=duration_ms,
                source_label=source_label,
                progress=_calc_progress(
                    node_key, "completed", self._node_order,
                ),
            )
            events.append(event)
            self._completed_nodes.add(node_key)
        return events

    def flush(self) -> list[AnalysisStreamEvent]:
        """保留统一 Adapter 生命周期接口；当前没有延迟事件。"""
        return []

    def get_final_state(self) -> OperationState | None:
        """返回最后从 values 事件中获取的完整 State。"""
        return self._latest_full_state
