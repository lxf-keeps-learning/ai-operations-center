"""
Operation Stream Service — 运营分析流式执行入口。

执行流程（重构后）：
  compiled_graph.astream()
  → LangGraph StreamPart (mode, data)
  → LangGraphEventAdapter
  → AnalysisStreamEvent
  → SSE 字符串 → API StreamingResponse

核心变更：
  - 不再手动调用业务 Node，执行权完全交给 compiled graph。
  - LangGraphEventAdapter 负责事件转换，Service 不感知 LangGraph 内部协议。
  - Graph 的 Edge/ConditionalEdge 决定真实执行路径。
"""

import logging
import time
from typing import Any, AsyncGenerator

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.langgraph_event_adapter import LangGraphEventAdapter
from app.analysis_stream.schemas import AnalysisStreamEvent
from app.db.session import get_session_local
from app.operation_agent.graph import NODE_METADATA, operation_graph
from app.operation_agent.models.analysis_event_model import AnalysisEvent
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.services.record_service import save_analysis_result
from app.operation_agent.state import OperationState
from app.utils.ids import new_trace_id

logger = logging.getLogger(__name__)

NODE_ORDER = list(NODE_METADATA.keys())


def _append_event(state: OperationState, event: AnalysisStreamEvent) -> None:
    log: list[dict[str, Any]] = state.setdefault("event_log", [])
    log.append(dict(event))


def _emit_event(
    state: OperationState,
    emitter: SseEventEmitter,
    event: AnalysisStreamEvent,
) -> str:
    _append_event(state, event)
    _persist_event(state, event)
    return emitter.format(event)


async def stream_operation_analysis(
    request: OperationAnalyzeRequest,
    emitter: SseEventEmitter,
    user_context: dict | None = None,
) -> AsyncGenerator[str, None]:
    """流式执行运营分析，由 compiled graph 驱动节点执行顺序。"""
    page_context = {
        "domain": request.domain,
        "active_tab": request.active_tab,
        "time_dimension": request.time_dimension,
        "date": request.date,
        "company_id": request.company_id,
        "project_id": request.project_id,
        "trigger_type": request.trigger_type,
        "user_question": request.user_question,
    }

    initial_state: OperationState = {
        "trace_id": emitter.run_id,
        "trigger_type": request.trigger_type,
        "user_question": request.user_question,
        "user_context": user_context or {},
        "page_context": page_context,
        "llm_usages": [],
        "event_log": [],
        "_streaming": True,
    }

    overall_start = time.monotonic()

    # ── analysis_started ──────────────────────────────────
    yield _emit_event(
        initial_state,
        emitter,
        emitter.create_analysis_started(
            "本质安全 AI 分析开始",
            payload={"page_context": page_context},
        ),
    )

    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)
    current_node_key: str | None = None
    current_node_name: str | None = None

    try:
        # ── compiled graph 是唯一执行源 ─────────────────
        async for mode, data in operation_graph.astream(
            initial_state,
            stream_mode=["values", "updates", "custom"],
        ):
            if mode == "values":
                for _event in adapter.process(mode, data):
                    yield _emit_event(initial_state, emitter, _event)
                continue

            if mode == "custom":
                if isinstance(data, dict) and data.get("kind") == "node_started":
                    current_node_key = data.get("node_key", "")
                    meta = NODE_METADATA.get(current_node_key, {})
                    current_node_name = meta.get("name", current_node_key)

            for _event in adapter.process(mode, data):
                yield _emit_event(initial_state, emitter, _event)

    except Exception as e:
        error_message = str(e)
        logger.exception("Graph 执行异常（节点 %s）", current_node_key)

        node_key = current_node_key or "unknown"
        node_name = current_node_name or node_key
        yield _emit_event(
            initial_state,
            emitter,
            emitter.create_node_failed(
                node_key=node_key,
                node_name=node_name,
                message=f"{node_name}失败",
                error_code=f"NODE_{node_key.upper()}_FAILED",
                error_message=error_message,
            ),
        )
        yield _emit_event(
            initial_state,
            emitter,
            emitter.create_analysis_failed(
                message="分析任务执行失败",
                error_code="NODE_FAILED",
                error_message=error_message,
            ),
        )
        yield _emit_event(initial_state, emitter, emitter.create_stream_closed())
        return

    # ── 清理 Adapter 缓存 ──────────────────────────────────
    for _event in adapter.flush():
        yield _emit_event(initial_state, emitter, _event)

    # ── 获取最终 State ──────────────────────────────────────
    final_state = adapter.get_final_state() or initial_state

    total_ms = int((time.monotonic() - overall_start) * 1000)
    trace_id = final_state.get("trace_id", new_trace_id())
    errors = final_state.get("errors", [])
    status = (
        "failed" if errors and not final_state.get("final_answer")
        else "partial" if errors
        else "success"
    )
    error_msg = errors[0].get("message") if errors else None

    # ── 持久化分析结果 ────────────────────────────────────
    db = None
    try:
        db = get_session_local()()
        saved = save_analysis_result(
            db,
            trace_id=trace_id,
            page_context=page_context,
            input_snapshot=(
                {"message": request.user_question}
                if request.user_question
                else {}
            ),
            result=final_state,
            status=status,
            error_message=error_msg,
            user_context=user_context,
        )
        final_state["record_id"] = saved.id
    except Exception:
        logger.exception("保存分析结果失败")
    finally:
        if db is not None:
            db.close()

    # ── report_completed ──────────────────────────────────
    report_payload = {
        "record_id": final_state.get("record_id"),
        "trace_id": trace_id,
        "status": status,
        "total_duration_ms": total_ms,
        "summary": final_state.get("final_answer", ""),
        "abnormal_items": final_state.get("abnormal_items", []),
        "risk_items": final_state.get("risk_items", []),
        "advice_items": final_state.get("advice_items", []),
        "evidence": final_state.get("evidence", []),
        "analysis_basis": final_state.get("analysis_basis", {}),
        "errors": final_state.get("errors", []),
    }
    yield _emit_event(
        final_state,
        emitter,
        emitter.create_report_completed(
            message="本质安全 AI 分析报告生成完成",
            payload=report_payload,
            duration_ms=total_ms,
        ),
    )

    # ── stream_closed ───────────────────────────────────
    yield _emit_event(final_state, emitter, emitter.create_stream_closed())


def _persist_event(state: OperationState, event: AnalysisStreamEvent) -> None:
    """将单条已发送事件持久化到 analysis_events 表。"""
    if state.get("_event_persistence_disabled"):
        return

    db = None
    try:
        db = get_session_local()()
        db.add(
            AnalysisEvent(
                run_id=event["run_id"],
                event_id=event["event_id"],
                sequence=int(event["sequence"]),
                event_type=event["event_type"],
                node_key=event.get("node_key"),
                node_name=event.get("node_name"),
                status=event.get("status"),
                message=event.get("message", "")[:255],
                duration_ms=event.get("duration_ms"),
                source_label=event.get("source_label"),
                payload_json=event.get("payload"),
                error_code=event.get("error_code"),
                error_message=event.get("error_message"),
                event_timestamp=event["timestamp"],
            )
        )
        db.commit()
    except Exception:
        if db is not None:
            db.rollback()
        state["_event_persistence_disabled"] = True
        logger.warning(
            "持久化分析事件失败，后续事件仅保留在内存 event_log: run_id=%s event_id=%s",
            event.get("run_id"),
            event.get("event_id"),
            exc_info=True,
        )
    finally:
        if db is not None:
            db.close()
