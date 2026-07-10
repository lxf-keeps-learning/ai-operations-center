# 工具领域契约模块
#
# 定义 Tool 框架的数据结构：
# - ToolContext：调用上下文（身份、租户、链路）
# - BaseToolInput：基础入参（context + filters）
# - Evidence：证据来源，用于 Agent 回答时追溯数据出处
# - ToolError：结构化错误信息
# - ToolResult：所有 Tool 统一返回结构
#
# 这些是 Tool 与 LangGraph、Agent、Tool Executor 之间的内部执行协议，
# 不是 HTTP API 的通用 DTO。API 层需要返回 ToolResult 时，应使用
# app/core/schema 中的全局 ApiResponse 进行包装。

from typing import Any

from pydantic import BaseModel, Field


class ToolContext(BaseModel):
    """Tool 调用上下文。

    这里只放调用身份、租户、请求链路等上下文信息，不放业务查询条件。
    """

    user_id: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    request_id: str | None = None
    locale: str = "zh-CN"


class BaseToolInput(BaseModel):
    """所有 Tool 的基础入参。

    filters 是 Query Tool 的统一过滤入口；如果后续某个 Tool 需要强类型入参，
    可以继承 BaseToolInput 并继续保留 context / filters 这两个基础字段。
    """

    context: ToolContext = Field(default_factory=ToolContext)
    filters: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Tool 返回数据的证据来源。

    Agent 最终回答用户时，应能通过 evidence 说明"这些结论来自哪里"。
    """

    source: str
    source_type: str
    record_id: str | None = None
    timestamp: str | None = None
    description: str | None = None


class ToolError(BaseModel):
    """Tool 失败时的结构化错误。

    Graph 不应该靠字符串猜异常，而是读取 code / retryable 决定下一步。
    """

    code: str
    message: str
    detail: dict | None = None
    retryable: bool = False


class ToolResult(BaseModel):
    """Tool 的唯一标准返回结构。

    Query Tool、Analysis Tool、Action Tool 都应返回这个结构，避免 Graph 处理多套协议。
    """

    success: bool
    data: dict | list | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    error: ToolError | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
