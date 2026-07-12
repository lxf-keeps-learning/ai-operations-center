"""
Trace 中间件 — 每个 HTTP 请求的入口与出口

职责：
  1. 生成/复用 traceId（优先使用前端传入的 X-Trace-Id 头）
  2. 初始化三层上下文（RequestContext / UserContext / PageContext）
  3. 请求结束后清理上下文（防止内存泄漏和上下文串扰）
  4. 将 traceId 写入响应头 X-Trace-Id

UserContext 和 PageContext 从请求头中解析，便于网关透传身份信息。
"""

from datetime import UTC, datetime

from fastapi import Request

from app.core.context.context_holder import (
    clear_all,
    set_page_context,
    set_request_context,
    set_user_context,
)
from app.core.context.page_context import PageContext
from app.core.context.request_context import RequestContext
from app.core.context.user_context import UserContext
from app.core.trace.trace_context import clear_trace_id, set_trace_id
from app.utils.ids import new_trace_id

# 前端可通过此请求头传入 traceId，后端复用；未传入则由后端自动生成
TRACE_ID_HEADER = "X-Trace-Id"

MCP_SKIP_PREFIXES = ("/mcp",)


def _should_skip(path: str) -> bool:
    return any(path.startswith(p) for p in MCP_SKIP_PREFIXES)


def _split_header(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def register_trace_middleware(app):
    """注册 Trace 中间件到 FastAPI 应用"""

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        """每个 HTTP 请求处理前初始化上下文，请求结束后清理"""

        if _should_skip(request.url.path):
            return await call_next(request)

        trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id()
        set_trace_id(trace_id)
        set_request_context(
            RequestContext(
                trace_id=trace_id,
                request_time=datetime.now(UTC),
                client_ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                method=request.method,
                path=request.url.path,
            )
        )
        set_user_context(
            UserContext(
                user_id=request.headers.get("X-User-Id", "anonymous"),
                username=request.headers.get("X-Username", "anonymous"),
                org_id=request.headers.get("X-Org-Id", ""),
                roles=_split_header(request.headers.get("X-Roles")),
                permissions=_split_header(request.headers.get("X-Permissions")),
            )
        )
        set_page_context(
            PageContext(
                page_code=request.headers.get("X-Page-Code", "infra_console"),
                selected_object_id=request.headers.get("X-Selected-Object-Id", ""),
            )
        )

        try:
            response = await call_next(request)
            response.headers[TRACE_ID_HEADER] = trace_id
            return response
        finally:
            clear_all()
            clear_trace_id()
