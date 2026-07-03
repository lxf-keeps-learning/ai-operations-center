from contextvars import ContextVar

from app.core.context.page_context import PageContext
from app.core.context.request_context import RequestContext
from app.core.context.user_context import UserContext
from app.core.trace.trace_context import get_trace_id

_request_ctx_var: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())
_user_ctx_var: ContextVar[UserContext] = ContextVar("user_context", default=UserContext())
_page_ctx_var: ContextVar[PageContext] = ContextVar("page_context", default=PageContext())


def get_request_context() -> RequestContext:
    ctx = _request_ctx_var.get()
    if not ctx.trace_id:
        ctx.trace_id = get_trace_id()
    return ctx


def set_request_context(ctx: RequestContext) -> None:
    _request_ctx_var.set(ctx)


def get_user_context() -> UserContext:
    return _user_ctx_var.get()


def set_user_context(ctx: UserContext) -> None:
    _user_ctx_var.set(ctx)


def get_page_context() -> PageContext:
    return _page_ctx_var.get()


def set_page_context(ctx: PageContext) -> None:
    _page_ctx_var.set(ctx)


def clear_all() -> None:
    _request_ctx_var.set(RequestContext())
    _user_ctx_var.set(UserContext())
    _page_ctx_var.set(PageContext())
