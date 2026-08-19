from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.core.context.context_holder import get_user_context
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import (
    DB_CONNECTION_ERROR,
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    RATE_LIMIT,
)
from app.core.schema.response_schema import ApiResponse
from app.tool_center.contracts import ToolContext
from app.tool_center.exceptions import (
    CapabilityUnavailableError,
    RegistryConfigurationError,
    RegistryUnavailableError,
    ToolForbiddenError,
    ToolNotFoundError,
    ToolRateLimitedError,
)
from app.tool_registry.compat import discover_tools, execute_tool

router = APIRouter(tags=["Tool Center"])


class ToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    # context 仅用于读取 locale；身份字段一律来自中间件 UserContext，忽略请求体伪造
    context: ToolContext = Field(default_factory=ToolContext)
    filters: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    confirmation_token: str | None = None
    stable_only: bool = False


class ToolDescriptor(BaseModel):
    name: str
    description: str


@router.get("/tools", response_model=ApiResponse[list[ToolDescriptor]])
def get_tools() -> ApiResponse[list[ToolDescriptor]]:
    user = get_user_context()
    tools = discover_tools(
        ToolContext(
            user_id=user.user_id,
            tenant_id=user.org_id or None,
            role=user.roles[0] if user.roles else None,
            caller_type="external",
        )
    )
    return ApiResponse(
        data=[
            ToolDescriptor(name=tool.name, description=tool.description)
            for tool in tools
        ]
    )


@router.post("/tools/call", response_model=ApiResponse[dict])
def call_tool(payload: ToolCallRequest) -> ApiResponse[dict]:
    user = get_user_context()
    context = ToolContext(
        user_id=user.user_id,
        tenant_id=user.org_id or None,
        role=user.roles[0] if user.roles else None,
        caller_type="external",
        locale=payload.context.locale or "zh-CN",
    )
    merged_filters = {**payload.filters, **payload.params}
    try:
        result = execute_tool(
            payload.tool_name,
            merged_filters,
            context,
            confirmation_token=payload.confirmation_token,
            stable_only=payload.stable_only,
        )
    except ToolNotFoundError as exc:
        raise AppException.from_error_code(NOT_FOUND, message=exc.message) from exc
    except CapabilityUnavailableError as exc:
        raise AppException.from_error_code(NOT_FOUND, message=exc.message) from exc
    except ToolForbiddenError as exc:
        raise AppException.from_error_code(FORBIDDEN, message=exc.message) from exc
    except ToolRateLimitedError as exc:
        retry_after = None
        if exc.detail:
            retry_after = exc.detail.get("retry_after_seconds")
        message = exc.message
        if retry_after is not None:
            message = f"{exc.message}; retry after {retry_after}s"
        raise _rate_limit_exception(message, retry_after) from exc
    except RegistryUnavailableError as exc:
        raise AppException.from_error_code(DB_CONNECTION_ERROR, message=exc.message) from exc
    except RegistryConfigurationError as exc:
        raise AppException.from_error_code(INTERNAL_ERROR, message=exc.message) from exc

    if result.success:
        return ApiResponse(data=result.model_dump())
    error_code = result.error.code if result.error else "TOOL_INTERNAL_ERROR"
    if error_code == "TOOL_CONFIRMATION_REQUIRED":
        # 确认挑战随标准响应包返回，客户端需携带 X-Trace-Id 重试同一挑战
        return ApiResponse(data=result.model_dump())
    if error_code == "TOOL_FORBIDDEN":
        raise AppException.from_error_code(
            FORBIDDEN,
            message=result.error.message if result.error else "forbidden",
        )
    if error_code == "TOOL_RATE_LIMITED":
        retry_after = None
        if result.error and result.error.detail:
            retry_after = result.error.detail.get("retry_after_seconds")
        message = result.error.message if result.error else "rate limited"
        if retry_after is not None:
            message = f"{message}; retry after {retry_after}s"
        raise _rate_limit_exception(message, retry_after)
    if error_code == "TOOL_CAPABILITY_UNAVAILABLE":
        raise AppException.from_error_code(
            NOT_FOUND,
            message=result.error.message if result.error else "capability unavailable",
        )
    if error_code == "TOOL_REGISTRY_UNAVAILABLE":
        raise AppException.from_error_code(
            DB_CONNECTION_ERROR,
            message=result.error.message if result.error else "registry unavailable",
        )
    if error_code == "TOOL_REGISTRY_CONFIGURATION_ERROR":
        raise AppException.from_error_code(
            INTERNAL_ERROR,
            message=result.error.message if result.error else "registry configuration error",
        )
    # 其余工具执行失败保持原有行为：随标准响应包返回执行结果
    return ApiResponse(data=result.model_dump())


def _rate_limit_exception(
    message: str,
    retry_after_seconds: int | None,
) -> AppException:
    data = (
        {"retry_after_seconds": retry_after_seconds}
        if retry_after_seconds is not None
        else None
    )
    headers = (
        {"Retry-After": str(retry_after_seconds)}
        if retry_after_seconds is not None
        else None
    )
    return AppException.from_error_code(
        RATE_LIMIT,
        message=message,
        data=data,
        headers=headers,
    )
