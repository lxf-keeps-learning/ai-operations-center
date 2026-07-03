from fastapi import Request

from app.core.trace.trace_context import clear_trace_id, set_trace_id
from app.utils.ids import new_trace_id

TRACE_ID_HEADER = "X-Trace-Id"


def register_trace_middleware(app):
    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id()
        set_trace_id(trace_id)

        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id

        clear_trace_id()
        return response
