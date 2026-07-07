import traceback

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exception.base_exception import AppException
from app.tool_center.core.exceptions import ToolException
from app.core.exception.error_code import FORBIDDEN, INTERNAL_ERROR, NOT_FOUND, PARAM_ERROR, RATE_LIMIT, UNAUTHORIZED, VALIDATION_ERROR
from app.core.logging.logger import get_logger
from app.core.schema.response_schema import ApiResponse
from app.core.trace.trace_context import get_trace_id
from app.utils.ids import new_trace_id

logger = get_logger("ioc.exception")

_HTTP_TO_ERROR_CODE: dict[int, int] = {
    400: PARAM_ERROR.code,
    401: UNAUTHORIZED.code,
    403: FORBIDDEN.code,
    404: NOT_FOUND.code,
    422: VALIDATION_ERROR.code,
    429: RATE_LIMIT.code,
}


def _ensure_trace_id() -> str:
    tid = get_trace_id()
    if tid:
        return tid
    return new_trace_id()


def _build_response(code: int, message: str, http_status: int) -> JSONResponse:
    trace_id = _ensure_trace_id()
    return JSONResponse(
        status_code=http_status,
        headers={"X-Trace-Id": trace_id},
        content=ApiResponse(
            code=code,
            message=message,
            trace_id=trace_id,
            data=None,
        ).model_dump(by_alias=True),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning("AppException: code=%s message=%s", exc.code, exc.message)
    trace_id = _ensure_trace_id()
    return JSONResponse(
        status_code=exc.http_status,
        headers={"X-Trace-Id": trace_id},
        content=ApiResponse(
            code=exc.code,
            message=exc.message,
            trace_id=trace_id,
            data=exc.data,
        ).model_dump(by_alias=True),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = _HTTP_TO_ERROR_CODE.get(exc.status_code, INTERNAL_ERROR.code)
    logger.warning("HTTPException: status=%s code=%s detail=%s", exc.status_code, code, exc.detail)
    return _build_response(code=code, message=str(exc.detail) or "请求处理失败", http_status=exc.status_code)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    logger.warning("RequestValidationError: detail=%s", errors)
    return _build_response(code=VALIDATION_ERROR.code, message=VALIDATION_ERROR.message, http_status=422)


async def tool_exception_handler(request: Request, exc: ToolException) -> JSONResponse:
    logger.warning("ToolException: code=%s message=%s retryable=%s", exc.code, exc.message, exc.retryable)
    return _build_response(code=INTERNAL_ERROR.code, message=exc.message, http_status=500)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled Exception: %s traceId=%s\n%s",
        exc,
        _ensure_trace_id(),
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    return _build_response(code=INTERNAL_ERROR.code, message="系统内部错误", http_status=500)


def register_exception_handlers(app):
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ToolException, tool_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
