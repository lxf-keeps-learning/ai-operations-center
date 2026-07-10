"""
finalize — 会话结束节点。

Graph 的最后一个节点，负责：
  1. 根据 LLM 调用结果更新 Session 状态（success / failed）
  2. 记录 runtime finish Span（标记全链路追踪的结束）
"""
from app.runtime.schemas.session_schema import SessionUpdate
from app.runtime.schemas.status import SESS_FAILED, SESS_SUCCESS
from app.runtime.schemas.trace_schema import TraceCreate
from app.runtime.services.session_service import session_service
from app.runtime.services.trace_service import trace_service
from app.runtime.state import RuntimeGraphState
from app.utils.ids import new_span_id


def finalize_node(state: RuntimeGraphState) -> RuntimeGraphState:
    """更新 Session 并记录 runtime finish Span。"""
    db = state["db"]
    trace_id = state["trace_id"]
    session_id = state["session_id"]
    root_span_id = state["root_span_id"]
    llm_result = state["llm_result"]
    answer = state["answer"]

    if llm_result.success:
        # LLM 调用成功：更新输出文本，标记 Session 为 success
        session_service.update_output(db, session_id, answer, status=SESS_SUCCESS)
        trace_service.create(
            db,
            TraceCreate(
                trace_id=trace_id,
                span_id=new_span_id(),
                parent_span_id=root_span_id,
                session_id=session_id,
                span_type="runtime",
                input_data={"event": "session_finished"},
                output_data={"status": SESS_SUCCESS},
                status="success",
            ),
        )
    else:
        # LLM 调用失败：记录错误信息，标记 Session 为 failed
        session_service.update(
            db,
            session_id,
            SessionUpdate(status=SESS_FAILED, error_message=llm_result.error_message),
        )
        trace_service.create(
            db,
            TraceCreate(
                trace_id=trace_id,
                span_id=new_span_id(),
                parent_span_id=root_span_id,
                session_id=session_id,
                span_type="runtime",
                input_data={"event": "session_finished"},
                output_data={"status": SESS_FAILED, "error": llm_result.error_message},
                status="failed",
            ),
        )

    return state
