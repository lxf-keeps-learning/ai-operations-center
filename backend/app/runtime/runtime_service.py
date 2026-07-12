"""
RuntimeService — AI Runtime 对话业务编排入口

使用 LangGraph StateGraph 编排完整对话流程：
  START → init_session → load_prompt → call_llm → finalize → END

所有关键步骤写入 ai_trace 表，支持全链路追踪。
chat_stream 方法通过 compiled_graph.astream() 以 SSE 流式输出 LLM Token。
"""

from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.runtime.graph import runtime_graph
from app.runtime.runtime_event_adapter import RuntimeEventAdapter
from app.runtime.schemas.feedback_schema import FeedbackCreate
from app.runtime.services.feedback_service import feedback_service
from app.runtime.state import RuntimeGraphState
from app.utils.sse import to_sse


class RuntimeService:
    """AI Runtime 对话编排服务

    使用 LangGraph StateGraph 编排对话流程，包含会话管理、Prompt 加载、
    LLM 调用、Trace 全链路追踪和 Session 状态管理。

    Streaming 使用 compiled_graph.astream() + RuntimeEventAdapter。
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

        通过 compiled_graph.astream() 驱动节点执行，LLM token 经
        get_stream_writer() → RuntimeEventAdapter → SSE 实时输出。
        """
        initial_state: RuntimeGraphState = {
            "db": db,
            "user_id": user_id,
            "message": message,
            "conversation_id": conversation_id,
            "biz_type": biz_type,
            "prompt_code": prompt_code,
            "_streaming": True,
        }

        adapter = RuntimeEventAdapter()
        yield to_sse(*adapter.get_message_started())

        try:
            async for mode, data in runtime_graph.astream(
                initial_state,
                stream_mode=["values", "updates", "custom"],
            ):
                for event_type, event_data in adapter.process(mode, data):
                    yield to_sse(event_type, event_data)

            completed = adapter.get_completed_event()
            if completed:
                yield to_sse(*completed)

        except Exception as exc:
            yield to_sse(*adapter.get_failed_event(str(exc)))
        finally:
            yield to_sse(*adapter.get_closed_event())

    def submit_feedback(self, db: Session, payload: FeedbackCreate) -> dict:
        """提交用户反馈，返回反馈记录 ID"""
        fb = feedback_service.create(db, payload)
        return {"feedback_id": fb.id, "message": "反馈提交成功"}


runtime_service = RuntimeService()
