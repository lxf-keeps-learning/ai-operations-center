from contextvars import ContextVar

from app.core.context.page_context import PageContext
from app.core.context.request_context import RequestContext
from app.core.context.user_context import UserContext
from app.core.trace.trace_context import get_trace_id

_request_ctx_var: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)
_user_ctx_var: ContextVar[UserContext | None] = ContextVar("user_context", default=None)
_page_ctx_var: ContextVar[PageContext | None] = ContextVar("page_context", default=None)


def get_request_context() -> RequestContext:
    ctx = _request_ctx_var.get()
    return ctx or RequestContext(trace_id=get_trace_id())


def set_request_context(ctx: RequestContext) -> None:
    _request_ctx_var.set(ctx)


def get_user_context() -> UserContext:
    return _user_ctx_var.get() or UserContext(user_id="anonymous", username="anonymous")


def set_user_context(ctx: UserContext) -> None:
    _user_ctx_var.set(ctx)


def get_page_context() -> PageContext:
    return _page_ctx_var.get() or PageContext(page_code="infra_console")


def set_page_context(ctx: PageContext) -> None:
    _page_ctx_var.set(ctx)


def clear_all() -> None:
    _request_ctx_var.set(None)
    _user_ctx_var.set(None)
    _page_ctx_var.set(None)
