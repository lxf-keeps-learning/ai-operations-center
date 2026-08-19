"""
Operation Stream Service — 运营分析流式执行入口。

执行流程（重构后）：
  SsePump（整体期限 120s / Graph 115s / 空闲心跳 15s / 断连取消）
    → producer: compiled_graph.astream()
    → LangGraphEventAdapter
    → AnalysisStreamEvent
    → SSE 字符串 → API StreamingResponse

防卡死语义：
  - Graph 预算 report_graph_timeout_seconds 到期 → pump 取消 producer Task，
    Graph/Node/Tool/LLM 协程全部收到取消；best-effort 写入失败状态，
    依次发送 analysis_failed(REPORT_TIMEOUT) + stream_closed，且只发一次。
  - 空闲心跳 sse_heartbeat_interval_seconds 维持连接；客户端断连 → generator
    aclose → pump 取消 producer，资源清理。
  - 心跳事件不持久化（非业务事件）。
"""

import logging
import time
from typing import Any, AsyncGenerator

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.langgraph_event_adapter import LangGraphEventAdapter
from app.analysis_stream.schemas import AnalysisStreamEvent
from app.analysis_stream.sse_pump import SsePump
from app.config.settings import settings
from app.db.session import get_session_local
from app.modules.prompt_center.application.langgraph_integration import get_prompt_metadata
from app.observability import build_langsmith_config
from app.operation_agent.graph import (
    NODE_METADATA,
    RUNTIME_NODE_ORDER,
    build_runtime_node_order,
    operation_graph,
)
from app.operation_agent.models.analysis_event_model import AnalysisEvent
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.services.record_service import save_analysis_result
from app.operation_agent.state import OperationState
from app.security.content_moderator import ModerationAction, content_moderator
from app.utils.ids import new_trace_id
from app.utils.sse import to_sse

logger = logging.getLogger(__name__)

# Retain a stable default export while each stream uses its routed runtime order.
NODE_ORDER = list(RUNTIME_NODE_ORDER)


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
    """流式执行运营分析，由 SsePump 驱动 compiled graph 并防卡死。"""
    moderation = content_moderator.moderate(request.user_question) if request.user_question else None
    safe_user_question = (
        getattr(moderation, "masked_text", None) or request.user_question
        if moderation is not None else request.user_question
    )
    page_context = {
        "domain": request.domain,
        "active_tab": request.active_tab,
        "time_dimension": request.time_dimension,
        "date": request.date,
        "company_id": request.company_id,
        "project_id": request.project_id,
        "trigger_type": request.trigger_type,
        "user_question": safe_user_question,
    }

    initial_state: OperationState = {
        "trace_id": emitter.run_id,
        "trigger_type": request.trigger_type,
        "user_question": safe_user_question,
        "user_context": user_context or {},
        "page_context": page_context,
        "llm_usages": [],
        "event_log": [],
        "_streaming": True,
    }

    # ── analysis_started ──────────────────────────────────
    yield _emit_event(
        initial_state,
        emitter,
        emitter.create_analysis_started(
            "本质安全 AI 分析开始",
            payload={"page_context": page_context},
        ),
    )

    if moderation and moderation.action in (ModerationAction.BLOCK, ModerationAction.ESCALATE):
        yield _emit_event(
            initial_state,
            emitter,
            emitter.create_analysis_failed(
                message=moderation.message or "输入包含凭据或高风险敏感信息，已阻断分析。",
                error_code="INPUT_SECURITY_BLOCKED",
                error_message="输入未进入分析图、数据库或模型链路。",
            ),
        )
        yield _emit_event(initial_state, emitter, emitter.create_stream_closed())
        return

    pump = SsePump(
        lambda: _analysis_producer(
            initial_state,
            emitter,
            request,
            user_context or {},
        ),
        graph_timeout_seconds=settings.report_graph_timeout_seconds,
        overall_timeout_seconds=settings.report_generation_timeout_seconds,
        idle_timeout_seconds=settings.sse_idle_timeout_seconds,
        heartbeat_interval_seconds=settings.sse_heartbeat_interval_seconds,
        heartbeat_sse=to_sse("heartbeat", {"trace_id": emitter.run_id}),
        on_graph_timeout=lambda: _analysis_timeout_events(
            initial_state,
            emitter,
            page_context,
            user_context or {},
        ),
        on_failure=lambda exc: _analysis_failure_events(
            emitter,
            error_code="ANALYSIS_STREAM_FAILED",
            error_message=str(exc),
        ),
    )
    async for event in pump.run():
        yield event


async def _analysis_producer(
    initial_state: OperationState,
    emitter: SseEventEmitter,
    request: OperationAnalyzeRequest,
    user_context: dict,
) -> AsyncGenerator[str, None]:
    """Graph astream 事件生产者：输出业务事件并负责正常终止事件。"""
    overall_start = time.monotonic()

    adapter = LangGraphEventAdapter(
        emitter,
        NODE_METADATA,
        build_runtime_node_order(request.domain),
    )
    current_node_key: str | None = None
    current_node_name: str | None = None

    prompt_metadata = get_prompt_metadata(
        prompt_key="ioc.safety.analysis",
        environment="production",
    )

    try:
        # ── compiled graph 是唯一执行源 ─────────────────
        async for mode, data in operation_graph.astream(
            initial_state,
            config=build_langsmith_config(
                trace_id=emitter.run_id,
                graph_name="ioc_operation_analysis_graph",
                user_id=(user_context or {}).get("user_id"),
                metadata={
                    "domain": request.domain,
                    "trigger_type": request.trigger_type,
                    "company_ref": request.company_id,
                    "project_ref": request.project_id,
                    "streaming": True,
                    **prompt_metadata,
                    "agent_key": request.domain,
                },
            ),
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
            page_context=initial_state.get("page_context", {}),
            input_snapshot={
                "message": initial_state.get("user_question", ""),
                "raw_data": final_state.get("raw_data", {}),
            } if initial_state.get("user_question") or final_state.get("raw_data") else {},
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
    agent_key = final_state.get("active_agent") or final_state.get("supervisor_route")
    if isinstance(agent_key, str) and agent_key:
        report_payload["agent_key"] = agent_key
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


def _analysis_timeout_events(
    initial_state: OperationState,
    emitter: SseEventEmitter,
    page_context: dict,
    user_context: dict,
) -> list[str]:
    """Graph 超时：best-effort 写失败状态 + 发送终止事件（只发一次）。"""
    logger.warning("运营分析 Graph 超时，取消任务并写入失败状态: trace_id=%s", emitter.run_id)
    db = None
    try:
        db = get_session_local()()
        save_analysis_result(
            db,
            trace_id=emitter.run_id,
            page_context=page_context,
            input_snapshot={"message": page_context.get("user_question", "")},
            result={
                "trace_id": emitter.run_id,
                "raw_data": {},
                "metrics": [],
                "abnormal_items": [],
                "reason_analysis": "",
                "risk_items": [],
                "advice_items": [],
                "evidence": [],
                "analysis_basis": {},
                "final_answer": "",
                "llm_usages": [],
                "errors": [{"node": "report_generation", "message": "报告生成超时"}],
            },
            status="failed",
            error_message="报告生成超时",
            user_context=user_context,
        )
    except Exception:
        logger.exception("写入运营分析失败状态异常（不影响超时收尾）")
    finally:
        if db is not None:
            db.close()

    events = [
        _emit_event(
            initial_state,
            emitter,
            emitter.create_analysis_failed(
                message="分析任务超时",
                error_code="REPORT_TIMEOUT",
                error_message="报告生成超过时限，已停止分析",
            ),
        ),
        _emit_event(initial_state, emitter, emitter.create_stream_closed()),
    ]
    return events


def _analysis_failure_events(
    emitter: SseEventEmitter,
    *,
    error_code: str,
    error_message: str,
) -> list[str]:
    """producer 异常兜底：失败 + 关闭（只发一次）。"""
    return [
        emitter.emit_analysis_failed(
            message="分析任务执行失败",
            error_code=error_code,
            error_message=error_message,
        ),
        emitter.emit_stream_closed(),
    ]


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
