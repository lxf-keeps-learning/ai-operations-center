"""
上下文持有器 — 通过 ContextVar 在异步请求范围内安全存取三层上下文

使用 Python contextvars 实现，确保每个异步任务的上下文隔离。
提供 get / set / clear_all 三类操作，生命周期与 HTTP 请求一致。
三层上下文：RequestContext / UserContext / PageContext。
"""

from contextvars import ContextVar

from app.core.context.page_context import PageContext
from app.core.context.request_context import RequestContext
from app.core.context.user_context import UserContext
from app.core.trace.trace_context import get_trace_id

# ContextVar 确保异步框架（如 AsyncIO）下各请求的上下文互相隔离
_request_ctx_var: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)
_user_ctx_var: ContextVar[UserContext | None] = ContextVar("user_context", default=None)
_page_ctx_var: ContextVar[PageContext | None] = ContextVar("page_context", default=None)


def get_request_context() -> RequestContext:
    """获取当前请求的 RequestContext，未设置时返回带 trace_id 的默认实例"""
    ctx = _request_ctx_var.get()
    return ctx or RequestContext(trace_id=get_trace_id())


def set_request_context(ctx: RequestContext) -> None:
    """设置当前请求的 RequestContext"""
    _request_ctx_var.set(ctx)


def get_user_context() -> UserContext:
    """获取当前请求的 UserContext，未设置时返回匿名用户"""
    return _user_ctx_var.get() or UserContext(user_id="anonymous", username="anonymous")


def set_user_context(ctx: UserContext) -> None:
    """设置当前请求的 UserContext"""
    _user_ctx_var.set(ctx)


def get_page_context() -> PageContext:
    """获取当前请求的 PageContext，未设置时返回默认控制台页面"""
    return _page_ctx_var.get() or PageContext(page_code="infra_console")


def set_page_context(ctx: PageContext) -> None:
    """设置当前请求的 PageContext"""
    _page_ctx_var.set(ctx)


def clear_all() -> None:
    """清理所有上下文（请求结束时调用，防止内存泄漏和上下文串扰）"""
    _request_ctx_var.set(None)
    _user_ctx_var.set(None)
    _page_ctx_var.set(None)
