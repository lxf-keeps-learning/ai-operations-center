"""
Operation Stream Service — 运营分析流式执行入口。

按节点逐个执行 Graph 并发送 SSE 事件。同一份事件对象会同时进入
State.event_log、analysis_events 审计表和 SSE 输出，支持按 run_id + sequence
追溯、回放和审计。
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.schemas import AnalysisStreamEvent
from app.db.session import get_session_local
from app.operation_agent.graph import OPERATION_NODE_SPECS
from app.operation_agent.models.analysis_event_model import AnalysisEvent
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.services.record_service import save_analysis_result
from app.operation_agent.state import OperationState
from app.utils.ids import new_trace_id

logger = logging.getLogger(__name__)

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
    """流式执行运营分析，逐个节点执行并发射可审计事件。"""
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

    state: OperationState = {
        "trace_id": emitter.run_id,
        "trigger_type": request.trigger_type,
        "user_question": request.user_question,
        "user_context": user_context or {},
        "page_context": page_context,
        "llm_usages": [],
        "event_log": [],
    }

    overall_start = time.monotonic()
    total_nodes = len(OPERATION_NODE_SPECS)

    yield _emit_event(
        state,
        emitter,
        emitter.create_analysis_started(
            "本质安全 AI 分析开始",
            payload={"page_context": page_context},
        ),
    )

    for index, (node_key, node_name, node_func) in enumerate(OPERATION_NODE_SPECS):
        node_start = time.monotonic()
        progress_started = int(index * 100 / total_nodes)

        yield _emit_event(
            state,
            emitter,
            emitter.create_node_started(
                node_key=node_key,
                node_name=node_name,
                message=f"{node_name}中",
                progress=progress_started,
            ),
        )

        try:
            previous_event_log = state.get("event_log", [])
            persistence_disabled = state.get("_event_persistence_disabled")
            state = await asyncio.to_thread(node_func, state)
            state.setdefault("event_log", previous_event_log)
            if persistence_disabled:
                state["_event_persistence_disabled"] = persistence_disabled
        except Exception as e:
            duration_ms = int((time.monotonic() - node_start) * 1000)
            error_message = str(e)
            logger.exception("节点 %s 执行失败", node_key)

            yield _emit_event(
                state,
                emitter,
                emitter.create_node_failed(
                    node_key=node_key,
                    node_name=node_name,
                    message=f"{node_name}失败",
                    error_code=f"NODE_{node_key.upper()}_FAILED",
                    error_message=error_message,
                    duration_ms=duration_ms,
                ),
            )
            yield _emit_event(
                state,
                emitter,
                emitter.create_analysis_failed(
                    message="分析任务执行失败",
                    error_code="NODE_FAILED",
                    error_message=error_message,
                ),
            )
            yield _emit_event(state, emitter, emitter.create_stream_closed())
            return

        duration_ms = int((time.monotonic() - node_start) * 1000)
        progress_completed = int((index + 1) * 100 / total_nodes)
        source_label = _detect_source_label(state, node_key, duration_ms)
        yield _emit_event(
            state,
            emitter,
            emitter.create_node_completed(
                node_key=node_key,
                node_name=node_name,
                message=f"{node_name}完成 · {duration_ms}ms",
                duration_ms=duration_ms,
                source_label=source_label,
                progress=progress_completed,
            ),
        )

    total_ms = int((time.monotonic() - overall_start) * 1000)
    trace_id = state.get("trace_id", new_trace_id())
    errors = state.get("errors", [])
    status = "failed" if errors and not state.get("final_answer") else "partial" if errors else "success"
    error_msg = errors[0].get("message") if errors else None

    db = None
    try:
        db = get_session_local()()
        saved = save_analysis_result(
            db,
            trace_id=trace_id,
            page_context=page_context,
            input_snapshot={"message": request.user_question} if request.user_question else {},
            result=state,
            status=status,
            error_message=error_msg,
            user_context=user_context,
        )
        state["record_id"] = saved.id
    except Exception:
        logger.exception("保存分析结果失败")
    finally:
        if db is not None:
            db.close()

    report_payload = {
        "record_id": state.get("record_id"),
        "trace_id": trace_id,
        "status": status,
        "total_duration_ms": total_ms,
        "summary": state.get("final_answer", ""),
        "abnormal_items": state.get("abnormal_items", []),
        "risk_items": state.get("risk_items", []),
        "advice_items": state.get("advice_items", []),
        "evidence": state.get("evidence", []),
        "errors": state.get("errors", []),
    }
    yield _emit_event(
        state,
        emitter,
        emitter.create_report_completed(
            message="本质安全 AI 分析报告生成完成",
            payload=report_payload,
            duration_ms=total_ms,
        ),
    )
    yield _emit_event(state, emitter, emitter.create_stream_closed())


def _detect_source_label(state: OperationState, node_key: str, duration_ms: int) -> str:
    """根据节点类型和 State 内容识别数据来源标签。"""
    formatted_ms = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.1f}s"
    node_source_map = {
        "init_context": f"本地初始化 · {formatted_ms}",
        "query_operation_data": _data_source_label(state, formatted_ms),
        "detect_abnormal": f"规则引擎 · {formatted_ms}",
        "analyze_reason": _llm_source_label(state, formatted_ms),
        "generate_advice": _llm_source_label(state, formatted_ms),
        "summary": f"Markdown 渲染 · {formatted_ms}",
    }
    return node_source_map.get(node_key, f"Node · {formatted_ms}")


def _data_source_label(state: OperationState, formatted: str) -> str:
    """检测数据来源：Mock / Tool Center / 领域快照"""
    raw = state.get("raw_data", {})
    snapshot = raw.get("domain_snapshot")
    ioc = raw.get("ioc_summary")
    if snapshot:
        domain = snapshot.get("items", [{}])[0].get("domain", "")
        return f"Mock IOC · {formatted}"
    if ioc:
        return f"Tool Center · {formatted}"
    kpi = raw.get("kpi_items", [])
    alarms = raw.get("alarm_items", [])
    if kpi or alarms:
        return f"Tool Center · {formatted}"
    return f"Mock IOC · {formatted}"


def _llm_source_label(state: OperationState, formatted: str) -> str:
    """检测 LLM 来源"""
    usages = state.get("llm_usages", [])
    last_usage = usages[-1] if usages else {}
    model = last_usage.get("model_name", "deepseek-chat") if last_usage.get("success") else "deepseek-chat"
    if "deepseek" in str(model).lower():
        return f"DeepSeek · {formatted}"
    if "qwen" in str(model).lower():
        return f"Qwen · {formatted}"
    if "doubao" in str(model).lower():
        return f"Doubao · {formatted}"
    return f"LLM · {formatted}"


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
