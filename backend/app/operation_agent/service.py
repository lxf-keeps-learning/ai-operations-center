"""
OperationService — 运营分析业务入口。

职责：
1. 对 API 层屏蔽 Graph 的细节。
2. 将外部请求（OperationAnalyzeRequest）转换为内部 State。
3. 调用 OperationGraph.ainvoke() 执行分析流程，受 report_graph_timeout_seconds 约束。
4. 将分析结果持久化到 operation_analysis_record 表。
5. 支持 30 分钟内相同参数的缓存复用。
6. 返回完整的 OperationState 供 API 层提取结果。

超时语义：
  - Graph 执行预算 report_graph_timeout_seconds（默认 115s）到期 → 取消 Graph Task，
    取消穿透到 async Node / Tool / LLM；best-effort 写入失败状态后抛出
    ReportTimeoutError（HTTP 504 / 504102）。
  - 不会在超时后继续生成或保存成功报告。
"""
import asyncio
import logging
from typing import Any

from app.config.settings import settings
from app.core.timeout import ReportTimeoutError
from app.db.session import get_session_local
from app.modules.prompt_center.application.langgraph_integration import get_prompt_metadata
from app.observability import build_langsmith_config
from app.operation_agent.analysis_basis import build_analysis_basis
from app.operation_agent.graph import operation_graph
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.services.record_service import get_cached_result, save_analysis_result
from app.operation_agent.state import OperationState
from app.security.content_moderator import ModerationAction, content_moderator
from app.utils.ids import new_trace_id

logger = logging.getLogger(__name__)


async def analyze_operation(
    request: OperationAnalyzeRequest,
    user_context: dict | None = None,
    trace_id: str | None = None,
) -> OperationState:
    """
    执行一次运营分析（异步）。

    先检查 30 分钟内相同 cache_key 是否有缓存结果，有则直接返回。
    没有则执行 Graph（受 Deadline 约束），完成后保存结果到数据库。
    """
    user_q = request.user_question
    moderation = content_moderator.moderate(user_q) if user_q else None
    safe_user_q = (
        getattr(moderation, "masked_text", None) or user_q
        if moderation is not None else user_q
    )
    page_context = {
        "domain": request.domain,
        "active_tab": request.active_tab,
        "time_dimension": request.time_dimension,
        "date": request.date,
        "company_id": request.company_id,
        "project_id": request.project_id,
        "trigger_type": request.trigger_type,
        "user_question": safe_user_q,
    }

    if moderation and moderation.action in (ModerationAction.BLOCK, ModerationAction.ESCALATE):
        return _blocked_result(trace_id, request, user_context, page_context, moderation.message)

    if not request.force_refresh:
        db = None
        try:
            db = get_session_local()()
            cached = get_cached_result(db, page_context)
            if cached:
                return state_from_record(cached, page_context, user_context or {})
        except Exception:
            logger.warning("读取运营分析缓存失败，继续执行实时分析", exc_info=True)
        finally:
            if db is not None:
                db.close()

    user_q = safe_user_q

    initial_state: OperationState = {
        "trace_id": trace_id or new_trace_id(),
        "trigger_type": request.trigger_type,
        "user_question": user_q,
        "user_context": user_context or {},
        "page_context": page_context,
        "llm_usages": [],
    }

    prompt_metadata = get_prompt_metadata(
        prompt_key="ioc.safety.analysis",
        environment="production",
    )

    try:
        async with asyncio.timeout(settings.report_graph_timeout_seconds):
            result = await operation_graph.ainvoke(
                initial_state,
                config=build_langsmith_config(
                    trace_id=initial_state["trace_id"],
                    graph_name="ioc_operation_analysis_graph",
                    user_id=(user_context or {}).get("user_id"),
                    metadata={
                        "domain": request.domain,
                        "trigger_type": request.trigger_type,
                        "company_ref": request.company_id,
                        "project_ref": request.project_id,
                        "streaming": False,
                        **prompt_metadata,
                        "agent_key": request.domain,
                    },
                ),
            )
    except TimeoutError as exc:
        logger.warning(
            "运营分析 Graph 超时（预算 %.1fs），取消任务并写入失败状态: trace_id=%s",
            settings.report_graph_timeout_seconds,
            initial_state.get("trace_id"),
        )
        _persist_failed_result(
            trace_id=initial_state.get("trace_id") or new_trace_id(),
            page_context=page_context,
            user_context=user_context,
            error_message="报告生成超时",
        )
        raise ReportTimeoutError(detail={"trace_id": initial_state.get("trace_id")}) from exc
    except asyncio.CancelledError:
        raise
    trace_id = result.get("trace_id", new_trace_id())

    errors = result.get("errors", [])
    status = "failed" if errors and not result.get("final_answer") else "partial" if errors else "success"
    error_msg = errors[0].get("message") if errors else None

    db2 = None
    try:
        db2 = get_session_local()()
        saved = save_analysis_result(
            db2,
            trace_id=trace_id,
            page_context=page_context,
            input_snapshot={
                "message": user_q,
                "raw_data": result.get("raw_data", {}),
            } if user_q or result.get("raw_data") else {},
            result=result,
            status=status,
            error_message=error_msg,
            user_context=user_context,
        )
        result["record_id"] = saved.id
    except Exception:
        logger.warning("保存运营分析结果失败，返回未持久化结果", exc_info=True)
    finally:
        if db2 is not None:
            db2.close()

    return result


def _persist_failed_result(
    *,
    trace_id: str,
    page_context: dict,
    user_context: dict | None,
    error_message: str,
) -> None:
    """超时后的 best-effort 失败状态持久化（不保存成功报告）。"""
    db = None
    try:
        db = get_session_local()()
        save_analysis_result(
            db,
            trace_id=trace_id,
            page_context=page_context,
            input_snapshot={"message": page_context.get("user_question", "")},
            result={
                "trace_id": trace_id,
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
                "errors": [{"node": "report_generation", "message": error_message}],
            },
            status="failed",
            error_message=error_message,
            user_context=user_context,
        )
    except Exception:
        logger.warning("写入运营分析失败状态异常（不影响超时返回）", exc_info=True)
    finally:
        if db is not None:
            db.close()


def _blocked_result(
    trace_id: str | None,
    request: OperationAnalyzeRequest,
    user_context: dict | None,
    page_context: dict,
    message: str | None,
) -> OperationState:
    return {
        "trace_id": trace_id or new_trace_id(),
        "trigger_type": request.trigger_type,
        "user_question": page_context.get("user_question"),
        "user_context": user_context or {},
        "page_context": page_context,
        "raw_data": {},
        "metrics": [],
        "abnormal_items": [],
        "reason_analysis": "",
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "analysis_basis": {},
        "final_answer": message or "您的输入包含违规内容，已被系统拦截。",
        "llm_usages": [],
        "errors": [],
    }


def state_from_record(record, page_context: dict, user_context: dict) -> OperationState:
    state: OperationState = {
        "record_id": record.id,
        "trace_id": record.trace_id,
        "trigger_type": page_context.get("trigger_type", "tab_analysis"),
        "user_question": None,
        "user_context": user_context,
        "page_context": page_context,
        "raw_data": {},
        "metrics": (record.metrics_json or {}).get("items", []) if record.metrics_json else [],
        "abnormal_items": (record.abnormal_items_json or {}).get("items", []) if record.abnormal_items_json else [],
        "reason_analysis": record.final_answer_markdown or "",
        "risk_items": (record.risk_items_json or {}).get("items", []) if record.risk_items_json else [],
        "advice_items": (record.advice_items_json or {}).get("items", []) if record.advice_items_json else [],
        "evidence": (record.evidence_json or {}).get("items", []) if record.evidence_json else [],
        "analysis_basis": (
            (record.evidence_json or {}).get("analysis_basis", {})
            if record.evidence_json
            else {}
        ),
        "final_answer": record.final_answer_markdown or "",
        "llm_usages": [],
        "errors": [],
    }
    if not state["analysis_basis"]:
        state["analysis_basis"] = build_analysis_basis(state)
    return state
