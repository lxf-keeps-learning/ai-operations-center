"""
AgentService — AI Agent 业务编排服务

核心职责：
  1. 接收 API 层的 Chat / Analyze 请求，创建 AgentTask 并返回跟踪信息
  2. 管理会话（Conversation）和运行（Session）的生命周期
  3. 提供 SSE 流式事件推送，使用真实 LLM 流式输出 Token/Chunk
  4. 支持 Prompt 查询、用户反馈收集
  5. 会话列表/详情/删除等管理操作

架构位置：
  API (routes/agent.py) → AgentService (application/agent_service.py) → runtime_store / ChatOpenAI

当前状态：
  使用 InMemoryStore 作为数据存储，后续可替换为 MySQL + Redis。
  流式输出已接入真实 LLM（ChatOpenAI streaming）。
"""

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config.llm_settings import llm_settings
from app.core.trace.trace_context import get_trace_id
from app.runtime.in_memory_store import SessionRecord, runtime_store
from app.schemas.agent import AgentTaskResponse, AnalyzeRequest, ChatRequest, StreamEvent
from app.schemas.common import PaginatedResult
from app.schemas.conversation import ConversationDetail, ConversationSummary
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.prompt import PromptDetail
from app.utils.ids import new_conversation_id, new_feedback_id, new_session_id, new_trace_id

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """一次 AI 分析/对话任务的跟踪信息

    包含 conversation_id（会话标识）、session_id（运行标识）、trace_id（全链路追踪）、
    status（运行状态）、stream_url（SSE 流式地址）。

    前端收到 AgentTaskResponse 后，通过 stream_url 拉取 SSE 流获取实时结果。
    """

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
    """AI Agent 业务编排 — 对话、分析、流式输出、会话管理、反馈"""

    def __init__(self) -> None:
        self._llm: ChatOpenAI | None = None
        self._init_llm()

    def _init_llm(self) -> None:
        provider = llm_settings.get_provider("deepseek")
        if provider and provider.api_key:
            self._llm = ChatOpenAI(
                model=provider.model,
                api_key=provider.api_key,
                base_url=provider.base_url,
                max_tokens=provider.max_output_tokens,
                temperature=0.3,
                timeout=60,
                streaming=True,
            )

    def create_chat_task(self, payload: ChatRequest) -> AgentTask:
        """创建 AI 对话任务"""
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
        """创建 AI 分析任务"""
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

    async def stream_events(
        self,
        trace_id: str,
        session_id: str | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """SSE 流式事件推送 — 使用真实 LLM Token 流

        支持取消（cancel_event 触发时立即终止）、异常降级、最终消息持久化。
        """
        session = runtime_store.sessions_by_trace.get(trace_id)
        if session is None:
            yield StreamEvent(event="error", traceId=trace_id, code=404,
                              message="Trace 不存在，请先调用 /api/v1/agent/analyze 或 /api/v1/agent/chat。")
            return

        if session_id is not None and session.session_id != session_id:
            yield StreamEvent(event="error", traceId=trace_id, code=400,
                              message="sessionId 与 traceId 不匹配。")
            return

        if self._llm is None:
            yield StreamEvent(event="start", traceId=trace_id, message="analysis started")
            yield StreamEvent(event="progress", traceId=trace_id, stage="llm",
                              message="正在生成 AI 回答")
            yield StreamEvent(event="token", traceId=trace_id,
                              content="（AI 未配置 API Key，请先设置 DEEPSEEK_API_KEY）")
            async for event in self._yield_done_fallback_async(trace_id, session, "LLM not configured"):
                yield event
            return

        yield StreamEvent(event="start", traceId=trace_id, message="analysis started")
        yield StreamEvent(event="progress", traceId=trace_id, stage="llm",
                          message="正在生成 AI 回答")
        run_start = perf_counter()
        full_content = ""

        messages = [
            SystemMessage(content="你是智能运营中心 AI 助手，请用中文回答。"),
            HumanMessage(content=session.message or "你好"),
        ]

        try:
            if cancel_event and cancel_event.is_set():
                yield StreamEvent(event="cancelled", traceId=trace_id,
                                  message="用户取消了本次请求")
                return

            stream = self._llm.astream(messages)
            async for chunk in stream:
                if cancel_event and cancel_event.is_set():
                    yield StreamEvent(event="cancelled", traceId=trace_id,
                                      message="用户取消了本次请求")
                    runtime_store.set_session_status(trace_id, "cancelled")
                    return

                token = chunk.content or ""
                if token:
                    full_content += token
                    yield StreamEvent(event="token", traceId=trace_id, content=token)

            cost_ms = max(1, int((perf_counter() - run_start) * 1000))
            runtime_store.set_session_status(trace_id, "success")
            runtime_store.set_session_output(trace_id, full_content)

            yield StreamEvent(event="done", traceId=trace_id, status="success",
                              message=f"analysis finished · {cost_ms}ms",
                              duration_ms=cost_ms)

        except asyncio.CancelledError:
            logger.warning("Chat stream cancelled by client: trace_id=%s", trace_id)
            yield StreamEvent(event="cancelled", traceId=trace_id,
                              message="请求已被取消")
            runtime_store.set_session_status(trace_id, "cancelled")
        except Exception as e:
            logger.exception("Chat stream LLM error: trace_id=%s", trace_id)
            error_msg = str(e)
            yield StreamEvent(event="error", traceId=trace_id, code=500,
                              message=f"LLM 调用异常: {error_msg}")
            async for event in self._yield_done_fallback_async(trace_id, session, error_msg):
                yield event

    async def _yield_done_fallback_async(
        self, trace_id: str, session: SessionRecord, error_message: str
    ) -> AsyncGenerator[StreamEvent, None]:
        fallback = (
            f"（AI 深度解答暂不可用）\n\n"
            f"当前大模型调用失败: {error_message}。\n"
            f"已保存用户输入，可稍后重试。"
        )
        runtime_store.set_session_status(trace_id, "failed")
        runtime_store.set_session_output(trace_id, fallback)
        yield StreamEvent(event="done", traceId=trace_id, status="failed",
                          message="LLM 调用失败，已保存用户输入")

    def list_conversations(
        self,
        agent_code: str | None,
        page: int,
        page_size: int,
    ) -> PaginatedResult[ConversationSummary]:
        items, total = runtime_store.list_conversations(agent_code=agent_code, page=page, page_size=page_size)
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


agent_service = AgentService()
