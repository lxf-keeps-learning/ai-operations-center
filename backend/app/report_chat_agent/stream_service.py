"""Report Chat SSE 流式服务。

执行流程（重构后）：
  compiled_graph.astream()
  → LangGraph StreamPart (mode, data)
  → ReportChatEventAdapter
  → SSE 字符串 → API StreamingResponse

Graph 继续负责范围判断、报告证据、RAG 和持久化；LLM token 通过
get_stream_writer() 实时回传。Adapter 负责答案校正（流式 vs 最终）。
"""
import logging
from typing import AsyncGenerator

from app.db.session import get_session_local
from app.report_chat_agent.graph import report_chat_graph
from app.report_chat_agent.report_chat_event_adapter import ReportChatEventAdapter
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.service import save_report_chat_usage
from app.report_chat_agent.state import ReportChatState
from app.security.content_moderator import ModerationAction, content_moderator
from app.utils.sse import to_sse

logger = logging.getLogger(__name__)


async def stream_chat_message(
    *,
    session_id: str,
    report_id: int,
    question: str,
    user_id: str,
    trace_id: str,
) -> AsyncGenerator[str, None]:
    """流式报告问答，由 compiled graph astream 驱动。"""
    # ── 构建初始 State（复用 service 层逻辑） ──────────────
    db = get_session_local()()
    try:
        session = report_chat_repo.get_session(db, session_id)
        if session is None:
            raise ValueError(f"报告会话不存在: {session_id}")
        runtime_session = report_chat_repo.begin_turn(
            db,
            session=session,
            question=question,
            trace_id=trace_id,
        )
        runtime_session_id = runtime_session.id
    finally:
        db.close()

    initial_state: ReportChatState = {
        "trace_id": trace_id,
        "report_id": str(report_id),
        "conversation_id": session.conversation_id,
        "session_id": session_id,
        "runtime_session_id": runtime_session_id,
        "user_id": user_id,
        "user_question": question,
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_rag": False,
        "rag_reason": "",
        "rag_query": {},
        "rag_results": [],
        "rag_source_refs": [],
        "rag_sources": [],
        "used_rag": False,
        "merged_context": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
        "llm_usages": [],
        "_streaming": True,
    }

    # ── 安全检查 ──────────────────────────────────────────
    moderation = content_moderator.moderate(question)
    if moderation.action in (ModerationAction.BLOCK, ModerationAction.ESCALATE):
        initial_state["final_answer"] = (
            moderation.message or "您的输入包含违规内容，已被系统拦截。"
        )
        initial_state["question_scope"] = "out_of_scope"
        initial_state["answer_type"] = "boundary"
        blocked_db = get_session_local()()
        try:
            message = report_chat_repo.complete_turn(
                blocked_db,
                session_id=session_id,
                runtime_session_id=runtime_session_id,
                report_id=report_id,
                content=initial_state["final_answer"],
                trace_id=trace_id,
                question_scope="out_of_scope",
                answer_type="boundary",
                evidence_refs=[],
                query_scope={},
                used_rag=False,
                rag_source_refs=[],
                rag_sources=[],
            )
            initial_state["message_id"] = message.id
        finally:
            blocked_db.close()

        adapter = ReportChatEventAdapter(trace_id, session_id)
        yield to_sse(*adapter.get_message_started())
        adapter.process("values", initial_state)
        for event_t, event_d in adapter.finalize():
            yield to_sse(event_t, event_d)
        yield to_sse(*adapter.get_closed_event())
        return

    # ── compiled graph astream ─────────────────────────────
    adapter = ReportChatEventAdapter(trace_id, session_id)
    yield to_sse(*adapter.get_message_started())

    try:
        async for mode, data in report_chat_graph.astream(
            initial_state,
            stream_mode=["values", "updates", "custom"],
        ):
            for event_t, event_d in adapter.process(mode, data):
                yield to_sse(event_t, event_d)

        # ── 答案校正 + message_completed ─────────────────
        final_state = adapter.get_final_state()

        # 对最终答案做输出安全过滤
        if final_state:
            final_answer = final_state.get("final_answer", "")
            out_moderation = content_moderator.moderate_output(final_answer)
            if out_moderation.action == ModerationAction.MASK and out_moderation.masked_text:
                final_state["final_answer"] = out_moderation.masked_text
            elif out_moderation.action == ModerationAction.BLOCK:
                final_state["final_answer"] = (
                    out_moderation.message
                    or "AI 生成的回答已被安全策略过滤，请尝试重新提问。"
                )
                final_state["answer_type"] = "boundary"

            save_report_chat_usage(final_state)

        for event_t, event_d in adapter.finalize():
            yield to_sse(event_t, event_d)

    except Exception as exc:
        logger.exception("Report Chat Graph 执行异常")
        yield to_sse(*adapter.get_failed_event(str(exc)))

    finally:
        yield to_sse(*adapter.get_closed_event())
