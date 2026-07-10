"""
RuntimeService — AI Runtime 对话业务编排入口

使用 LangGraph StateGraph 编排完整对话流程：
  START → init_session → load_prompt → call_llm → finalize → END

所有关键步骤写入 ai_trace 表，支持全链路追踪。
chat_stream 方法以 SSE 流式输出 LLM Token。
"""

import asyncio
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.runtime.graph import runtime_graph
from app.runtime.schemas.feedback_schema import FeedbackCreate
from app.runtime.services.feedback_service import feedback_service
from app.runtime.state import RuntimeGraphState
from app.runtime.stream_context import use_llm_stream_callback
from app.utils.sse import to_sse


class RuntimeService:
    """AI Runtime 对话编排服务

    使用 LangGraph StateGraph 编排对话流程，包含会话管理、Prompt 加载、
    LLM 调用、Trace 全链路追踪和 Session 状态管理。
    """

    def chat(
        self,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        biz_type: str | None = None,
        prompt_code: str | None = None,
    ) -> dict:
        """执行一次 AI 对话的完整流程

        使用 runtime_graph.invoke() 编排，返回对话结果。
        """
        state: RuntimeGraphState = {
            "db": db,
            "user_id": user_id,
            "message": message,
            "conversation_id": conversation_id,
            "biz_type": biz_type,
            "prompt_code": prompt_code,
        }

        result = runtime_graph.invoke(state)

        return {
            "conversation_id": result["conversation"].id,
            "session_id": result["session_id"],
            "trace_id": result["trace_id"],
            "answer": result["answer"],
            "reply": result["answer"],
        }

    async def chat_stream(
        self,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        biz_type: str | None = None,
        prompt_code: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 AI 对话，以 SSE 格式逐 token 输出 LLM 回复。

        通过 ContextVar 将 streaming callback 传入 Graph 内部的 LLM 节点。
        Graph 整体在线程中执行，chunk 通过 asyncio.Queue 传递回协程。
        """
        state: RuntimeGraphState = {
            "db": db,
            "user_id": user_id,
            "message": message,
            "conversation_id": conversation_id,
            "biz_type": biz_type,
            "prompt_code": prompt_code,
        }

        loop = asyncio.get_running_loop()
        chunk_queue: asyncio.Queue[str] = asyncio.Queue()

        def on_chunk(text: str) -> None:
            if text:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, text)

        yield to_sse("message_started", {})

        try:
            graph_task = asyncio.create_task(
                asyncio.to_thread(
                    _invoke_graph_with_stream, state, on_chunk
                )
            )

            while not graph_task.done() or not chunk_queue.empty():
                try:
                    delta = await asyncio.wait_for(chunk_queue.get(), timeout=0.1)
                except TimeoutError:
                    continue
                yield to_sse("token", {"delta": delta})

            result = await graph_task

            yield to_sse("message_completed", {
                "conversation_id": result["conversation"].id,
                "session_id": result["session_id"],
                "trace_id": result["trace_id"],
                "answer": result["answer"],
            })
        except Exception as exc:
            yield to_sse("message_failed", {
                "error_message": str(exc),
            })
        finally:
            yield to_sse("stream_closed", {})

    def submit_feedback(self, db: Session, payload: FeedbackCreate) -> dict:
        """提交用户反馈，返回反馈记录 ID"""
        fb = feedback_service.create(db, payload)
        return {"feedback_id": fb.id, "message": "反馈提交成功"}


def _invoke_graph_with_stream(state: RuntimeGraphState, on_chunk) -> RuntimeGraphState:
    """在线程中执行 Graph，并注册 LLM streaming callback"""
    with use_llm_stream_callback(on_chunk):
        return runtime_graph.invoke(state)


runtime_service = RuntimeService()
