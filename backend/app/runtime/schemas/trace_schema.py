"""
Trace DTO — 全链路追踪的请求/响应数据结构

TraceCreate:   创建 Span 时的请求体（包含 traceId、spanId、父 Span、各环节信息）
TraceResponse: Trace 的响应体
"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class TraceCreate(IocBaseModel):
    trace_id: str = Field(min_length=1, max_length=64)
    span_id: str | None = Field(default=None, max_length=64)
    parent_span_id: str | None = Field(default=None, max_length=64)
    conversation_id: str | None = Field(default=None, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    span_type: str = Field(min_length=1, max_length=32)
    graph_name: str | None = Field(default=None, max_length=128)
    node_name: str | None = Field(default=None, max_length=128)
    tool_name: str | None = Field(default=None, max_length=128)
    model_name: str | None = Field(default=None, max_length=128)
    prompt_id: str | None = Field(default=None, max_length=64)
    prompt_code: str | None = Field(default=None, max_length=128)
    prompt_version: int | None = None
    prompt_snapshot: str | None = None
    input_data: dict | None = None
    output_data: dict | None = None
    cost_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    status: str = "running"
    error_code: str | None = None
    error_message: str | None = None


class TraceResponse(IocBaseModel):
    id: str
    trace_id: str
    span_id: str | None
    parent_span_id: str | None
    conversation_id: str | None
    session_id: str
    span_type: str
    graph_name: str | None
    node_name: str | None
    tool_name: str | None
    model_name: str | None
    prompt_id: str | None
    prompt_code: str | None
    prompt_version: int | None
    prompt_snapshot: str | None
    input_data: dict | None
    output_data: dict | None
    cost_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
