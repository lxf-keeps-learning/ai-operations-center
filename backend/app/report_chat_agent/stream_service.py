"""Report Chat SSE 流式服务。

Graph 继续负责范围判断、报告证据、RAG 和持久化；只有回答生成节点通过
ContextVar 回调真实模型 chunk。本服务将跨线程 chunk 转成 SSE，并在 Graph
完成后发送权威元数据，确保流式展示与最终落库内容一致。
"""

import asyncio
from typing import AsyncGenerator

from app.report_chat_agent.service import send_chat_message
from app.report_chat_agent.state import ReportChatState
from app.report_chat_agent.stream_context import use_answer_stream_callback
from app.security.content_moderator import ModerationAction, content_moderator
from app.utils.sse import to_sse


async def stream_chat_message(
    *,
    session_id: str,
    report_id: int,
    question: str,
    user_id: str,
    trace_id: str,
) -> AsyncGenerator[str, None]:
    loop = asyncio.get_running_loop()
    chunk_queue: asyncio.Queue[str] = asyncio.Queue()
    streamed_parts: list[str] = []
    sequence = 0

    def event(event_type: str, **payload: object) -> str:
        nonlocal sequence
        sequence += 1
        return to_sse(
            event_type,
            {
                "event_type": event_type,
                "sequence": sequence,
                "trace_id": trace_id,
                "session_id": session_id,
                **payload,
            },
        )

    def on_chunk(delta: str) -> None:
        if delta:
            loop.call_soon_threadsafe(chunk_queue.put_nowait, delta)

    def invoke_graph() -> ReportChatState:
        with use_answer_stream_callback(on_chunk):
            return send_chat_message(
                session_id=session_id,
                report_id=report_id,
                question=question,
                user_id=user_id,
                trace_id=trace_id,
            )

    graph_task = asyncio.create_task(asyncio.to_thread(invoke_graph))
    yield event("message_started", message="正在分析当前报告和相关依据")

    try:
        while not graph_task.done() or not chunk_queue.empty():
            try:
                delta = await asyncio.wait_for(chunk_queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            streamed_parts.append(delta)
            yield event("answer_delta", delta=delta)

        result = await graph_task
        final_answer = result.get("final_answer", "")
        moderation = content_moderator.moderate_output(final_answer)
        if moderation.action == ModerationAction.MASK and moderation.masked_text:
            final_answer = moderation.masked_text
        elif moderation.action == ModerationAction.BLOCK:
            final_answer = moderation.message or "AI 生成的回答已被安全策略过滤，请尝试重新提问。"
        streamed_answer = "".join(streamed_parts)

        # 边界回答、证据不足或模型中途失败时，Graph 的最终答案可能不是流中
        # 已发送内容。先 reset 再发送权威结果，保证页面与持久化消息一致。
        if final_answer != streamed_answer:
            if streamed_parts:
                yield event("answer_reset")
            if final_answer:
                yield event("answer_delta", delta=final_answer)

        yield event(
            "message_completed",
            message_id=result.get("message_id", ""),
            conversation_id=result.get("conversation_id", ""),
            runtime_session_id=result.get("runtime_session_id", ""),
            question_scope=result.get("question_scope", "report_internal"),
            answer=final_answer,
            answer_type=result.get("answer_type", "normal"),
            evidence_refs=result.get("evidence_refs", []),
            query_scope=result.get("query_scope", {}),
            used_rag=result.get("used_rag", False),
            rag_source_refs=result.get("rag_source_refs", []),
            rag_sources=result.get("rag_sources", []) or result.get("rag_results", []),
            errors=result.get("errors", []),
        )
        yield event("stream_closed")
    except Exception as exc:
        yield event(
            "message_failed",
            message="AI 深度解答生成失败",
            error_message=str(exc),
        )
        yield event("stream_closed")
