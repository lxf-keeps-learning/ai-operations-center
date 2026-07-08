from typing import Any

from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    session_id: str = Field(description="会话 ID")
    report_id: int = Field(description="报告 ID")
    title: str = Field(description="会话标题")


class ChatMessageResponse(BaseModel):
    role: str = Field(description="角色: user / assistant")
    content: str = Field(description="消息内容")
    evidence_refs: list[str] = Field(default_factory=list, description="引用的证据 ID")
    question_scope: str | None = Field(default=None, description="问题范围")
    created_at: str = Field(description="消息时间")
    used_rag: bool = Field(default=False, description="是否使用了 RAG 知识库补充")
    rag_source_refs: list[str] = Field(default_factory=list, description="RAG 引用的知识库来源 ID")
    rag_sources: list[dict[str, Any]] = Field(default_factory=list, description="RAG 知识库依据明细")


class GetMessagesResponse(BaseModel):
    session_id: str = Field(description="会话 ID")
    messages: list[ChatMessageResponse] = Field(default_factory=list, description="消息列表")


class SendMessageResponse(BaseModel):
    trace_id: str = Field(description="追踪 ID")
    session_id: str = Field(description="会话 ID")
    message_id: str = Field(description="消息 ID")
    question_scope: str = Field(description="问题范围")
    answer: str = Field(description="回答内容")
    evidence_refs: list[str] = Field(default_factory=list, description="引用的证据 ID")
    query_scope: dict[str, Any] = Field(default_factory=dict, description="报告扩展查询范围")
    answer_type: str = Field(default="normal", description="回答类型")
    used_rag: bool = Field(default=False, description="本轮回答是否使用了 RAG 知识库补充")
    rag_source_refs: list[str] = Field(default_factory=list, description="RAG 引用的知识库来源 ID")
    rag_sources: list[dict[str, Any]] = Field(default_factory=list, description="RAG 知识库依据明细")
