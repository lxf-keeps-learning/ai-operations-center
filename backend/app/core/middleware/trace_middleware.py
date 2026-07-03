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

TRACE_ID_HEADER = "X-Trace-Id"


def _split_header(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def register_trace_middleware(app):
    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
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
