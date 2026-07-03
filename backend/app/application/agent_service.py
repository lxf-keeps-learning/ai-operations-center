import asyncio
from dataclasses import dataclass

from app.core.trace.trace_context import get_trace_id
from app.runtime.in_memory_store import SessionRecord, runtime_store
from app.schemas.agent import AgentTaskResponse, AnalyzeRequest, ChatRequest, StreamEvent
from app.schemas.common import PaginatedResult
from app.schemas.conversation import ConversationDetail, ConversationSummary
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.prompt import PromptDetail
from app.utils.ids import new_conversation_id, new_feedback_id, new_session_id, new_trace_id


@dataclass
class AgentTask:
    conversation_id: str
    session_id: str
    trace_id: str
    status: str = "running"

    def to_response(self) -> AgentTaskResponse:
        return AgentTaskResponse(
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            status=self.status,
            stream_url=f"/api/v1/agent/stream?traceId={self.trace_id}",
        )


class AgentService:
    def create_chat_task(self, payload: ChatRequest) -> AgentTask:
        conversation_id = payload.conversation_id or new_conversation_id()
        task = self._create_task(
            conversation_id=conversation_id,
            agent_code=payload.agent_code,
            scene_code="chat",
            message=payload.message,
            title=payload.message[:30] or "AI 对话",
        )
        return task

    def create_analyze_task(self, payload: AnalyzeRequest) -> AgentTask:
        conversation_id = payload.conversation_id or new_conversation_id()
        title = payload.message or payload.scene_code
        task = self._create_task(
            conversation_id=conversation_id,
            agent_code=payload.agent_code,
            scene_code=payload.scene_code,
            message=payload.message,
            title=title[:30] or "AI 分析",
        )
        return task

    async def stream_events(self, trace_id: str, session_id: str | None = None):
        session = runtime_store.sessions_by_trace.get(trace_id)
        if session is None:
            yield StreamEvent(
                event="error",
                traceId=trace_id,
                code=404,
                message=(
                    "Trace 不存在，请先调用 /api/v1/agent/analyze "
                    "或 /api/v1/agent/chat。"
                ),
            )
            return

        if session_id is not None and session.session_id != session_id:
            yield StreamEvent(
                event="error",
                traceId=trace_id,
                code=400,
                message="sessionId 与 traceId 不匹配。",
            )
            return

        yield StreamEvent(event="start", traceId=trace_id, message="analysis started")
        await asyncio.sleep(0.1)
        yield StreamEvent(
            event="progress",
            traceId=trace_id,
            stage="query_tool",
            message="正在读取页面上下文",
        )
        await asyncio.sleep(0.1)
        yield StreamEvent(
            event="progress",
            traceId=trace_id,
            stage="analyze",
            message="正在生成分析摘要",
        )

        for chunk in self._mock_answer_chunks(session):
            await asyncio.sleep(0.08)
            yield StreamEvent(event="token", traceId=trace_id, content=chunk)

        runtime_store.set_session_status(trace_id, "success")
        yield StreamEvent(
            event="done",
            traceId=trace_id,
            status="success",
            message="analysis finished",
        )

    def list_conversations(
        self,
        agent_code: str | None,
        page: int,
        page_size: int,
    ) -> PaginatedResult[ConversationSummary]:
        items, total = runtime_store.list_conversations(
            agent_code=agent_code,
            page=page,
            page_size=page_size,
        )
        return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        return runtime_store.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        return runtime_store.delete_conversation(conversation_id)

    def get_prompt(self, prompt_code: str) -> PromptDetail | None:
        return runtime_store.prompts.get(prompt_code)

    def create_feedback(self, payload: FeedbackRequest) -> FeedbackResponse:
        feedback_id = new_feedback_id()
        runtime_store.feedback_ids.append(feedback_id)
        return FeedbackResponse(feedback_id=feedback_id)

    def _create_task(
        self,
        conversation_id: str,
        agent_code: str,
        scene_code: str,
        message: str | None,
        title: str,
    ) -> AgentTask:
        trace_id = get_trace_id() or new_trace_id()
        session_id = new_session_id()
        runtime_store.upsert_session(
            SessionRecord(
                session_id=session_id,
                trace_id=trace_id,
                conversation_id=conversation_id,
                agent_code=agent_code,
                scene_code=scene_code,
                message=message,
            ),
            title=title,
        )
        return AgentTask(conversation_id=conversation_id, session_id=session_id, trace_id=trace_id)

    def _mock_answer_chunks(self, session: SessionRecord) -> list[str]:
        scene_name = "运营分析" if session.agent_code == "operation" else "AI 分析"
        return [
            f"## {scene_name}摘要\n\n",
            f"- 当前任务：{session.scene_code}\n",
            f"- 用户问题：{session.message or '未提供'}\n",
            "- 初始化阶段已完成 REST + SSE 链路联调。\n",
            "- 后续可在 Application 层接入 LangGraph，并在 Tool Center 中访问 "
            "IOC 业务数据。\n\n",
            "建议下一步补充真实 Tool、Prompt 版本管理、Trace 入库和"
            "权限上下文。",
        ]


agent_service = AgentService()
