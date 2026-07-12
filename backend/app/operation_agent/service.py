"""
OperationService — 运营分析业务入口。

职责：
1. 对 API 层屏蔽 Graph 的细节。
2. 将外部请求（OperationAnalyzeRequest）转换为内部 State。
3. 调用 OperationGraph.invoke() 执行分析流程。
4. 将分析结果持久化到 operation_analysis_record 表。
5. 支持 30 分钟内相同参数的缓存复用。
6. 返回完整的 OperationState 供 API 层提取结果。
"""
import logging

from app.operation_agent.analysis_basis import build_analysis_basis
from app.db.session import get_session_local
from app.operation_agent.graph import operation_graph
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.services.record_service import get_cached_result, save_analysis_result
from app.operation_agent.state import OperationState
from app.security.content_moderator import ModerationAction, content_moderator
from app.utils.ids import new_trace_id

logger = logging.getLogger(__name__)


def analyze_operation(
    request: OperationAnalyzeRequest,
    user_context: dict | None = None,
    trace_id: str | None = None,
) -> OperationState:
    """
    执行一次运营分析。

    先检查 30 分钟内相同 cache_key 是否有缓存结果，有则直接返回。
    没有则执行 Graph，完成后保存结果到数据库。
    """
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

    user_q = request.user_question
    if user_q:
        moderation = content_moderator.moderate(user_q)
        if moderation.action in (ModerationAction.BLOCK, ModerationAction.ESCALATE):
            return _blocked_result(trace_id, request, user_context, page_context, moderation.message)

    initial_state: OperationState = {
        "trace_id": trace_id or new_trace_id(),
        "trigger_type": request.trigger_type,
        "user_question": user_q,
        "user_context": user_context or {},
        "page_context": page_context,
        "llm_usages": [],
    }

    result = operation_graph.invoke(initial_state)
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
            input_snapshot={"message": request.user_question} if request.user_question else {},
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
        "user_question": request.user_question,
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
