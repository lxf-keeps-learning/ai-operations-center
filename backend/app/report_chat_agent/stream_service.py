"""Report Chat SSE 流式服务。

执行流程（重构后）：
  SsePump（整体期限 / Graph 预算 / 空闲心跳 / 断连取消）
    → producer: compiled_graph.astream()
    → ReportChatEventAdapter
    → SSE 字符串 → API StreamingResponse

Graph 继续负责范围判断、报告证据、RAG 和持久化；LLM token 通过
get_stream_writer() 实时回传。Adapter 负责答案校正（流式 vs 最终）。

防卡死语义：
  - Graph 预算 report_graph_timeout_seconds 到期 → 取消 Graph Task，
    best-effort fail_turn 写失败状态，依次发送 message_failed(REPORT_TIMEOUT)
    + stream_closed（只发一次）。
  - 心跳 sse_heartbeat_interval_seconds 维持连接；客户端断连 → generator
    aclose → pump 取消 producer。
"""
import asyncio
import logging
from typing import AsyncGenerator

from app.analysis_stream.sse_pump import SsePump
from app.config.settings import settings
from app.db.session import get_session_local
from app.observability import build_langsmith_config
from app.report_chat_agent.graph import report_chat_graph
from app.report_chat_agent.report_chat_event_adapter import ReportChatEventAdapter
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.persistence import async_report_chat_graph
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
    """流式报告问答，由 SsePump 驱动 compiled graph astream。"""
    # ── 构建初始 State（复用 service 层逻辑） ──────────────
    db = get_session_local()()
    try:
        session = report_chat_repo.get_session(db, session_id)
        if session is None:
            raise ValueError(f"报告会话不存在: {session_id}")
        moderation = content_moderator.moderate(question)
        safe_question = getattr(moderation, "masked_text", None) or question
        sensitive_types = getattr(moderation, "sensitive_types", [])
        runtime_session = report_chat_repo.begin_turn(
            db,
            session=session,
            question=safe_question,
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
        "user_question": safe_question,
        "sensitive_data_detected": bool(sensitive_types),
        "credential_detected": (
            moderation.action == ModerationAction.BLOCK
            and bool(sensitive_types)
        ),
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "metrics": [],
        "analysis_basis": {},
        "raw_data": {},
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

    adapter = ReportChatEventAdapter(trace_id, session_id)
    yield to_sse(*adapter.get_message_started())

    # ── 安全检查 ──────────────────────────────────────────
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

        adapter.process("values", initial_state)
        for event_t, event_d in adapter.finalize():
            yield to_sse(event_t, event_d)
        yield to_sse(*adapter.get_closed_event())
        return

    # ── compiled graph astream（经 SsePump 防卡死） ────────
    pump = SsePump(
        lambda: _report_chat_producer(
            initial_state,
            adapter,
            session_id,
            user_id,
            report_id,
        ),
        graph_timeout_seconds=settings.report_graph_timeout_seconds,
        overall_timeout_seconds=settings.report_generation_timeout_seconds,
        idle_timeout_seconds=settings.sse_idle_timeout_seconds,
        heartbeat_interval_seconds=settings.sse_heartbeat_interval_seconds,
        heartbeat_sse=to_sse(
            "heartbeat",
            {"trace_id": trace_id, "session_id": session_id},
        ),
        on_graph_timeout=lambda: _report_chat_timeout_events(
            adapter,
            runtime_session_id=runtime_session_id,
        ),
        on_failure=lambda exc: _report_chat_failure_events(adapter, str(exc)),
    )
    async for event in pump.run():
        yield event


async def _report_chat_producer(
    initial_state: ReportChatState,
    adapter: ReportChatEventAdapter,
    session_id: str,
    user_id: str,
    report_id: int,
) -> AsyncGenerator[str, None]:
    """Graph astream 事件生产者：输出业务事件并负责正常终止事件。"""
    trace_id = initial_state["trace_id"]
    try:
        graph_config = build_langsmith_config(
            trace_id=trace_id,
            graph_name="ioc_report_chat_graph",
            user_id=user_id,
            session_id=session_id,
            conversation_id=initial_state["conversation_id"],
            metadata={
                "report_id": str(report_id),
                "scene": initial_state["scene"],
                "streaming": True,
            },
        )
        graph_config["configurable"] = {"thread_id": session_id}
        async with async_report_chat_graph(report_chat_graph) as graph:
            async for mode, data in graph.astream(
                initial_state,
                config=graph_config,
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
        yield to_sse(*adapter.get_closed_event())
        return

    yield to_sse(*adapter.get_closed_event())


def _report_chat_timeout_events(
    adapter: ReportChatEventAdapter,
    *,
    runtime_session_id: str,
) -> list[str]:
    """Graph 超时：best-effort fail_turn + message_failed + stream_closed（只发一次）。"""
    logger.warning("报告问答 Graph 超时，取消任务并写失败状态: runtime_session_id=%s", runtime_session_id)
    db = get_session_local()()
    try:
        report_chat_repo.fail_turn(
            db,
            runtime_session_id=runtime_session_id,
            error_message="报告生成超时",
        )
    except Exception:
        logger.exception("报告问答超时写失败状态异常（不影响超时收尾）")
    finally:
        db.close()

    return [
        to_sse(*adapter.get_failed_event("报告生成超过时限，已停止生成")),
        to_sse(*adapter.get_closed_event()),
    ]


def _report_chat_failure_events(adapter: ReportChatEventAdapter, error_message: str) -> list[str]:
    """producer 异常兜底：message_failed + stream_closed（只发一次）。"""
    return [
        to_sse(*adapter.get_failed_event(error_message)),
        to_sse(*adapter.get_closed_event()),
    ]
