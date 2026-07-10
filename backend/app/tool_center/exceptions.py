# 工具异常模块
#
# 定义工具框架的分层异常体系，异常均继承自项目全局 AppException。
# 每个异常包含：code（机器可读的错误码，工具层使用字符串标识）、
# message（人类可读的描述）、detail（可选的结构化详情）和 retryable（是否可重试）。
#
# Tool 异常与 HTTP API 响应的错误码分离：
# - tool_center/exceptions.py: Tool 内部执行协议，code 为字符串，用于 Graph 判断
# - app/core/exception: HTTP API 响应协议，code 为整数错误码，用于前端展示
# global exception_handler 统一拦截 ToolException 后以 INTERNAL_ERROR.code 返回

from app.core.exception.base_exception import AppException


class ToolException(AppException):
    """Tool 异常基类。

    所有工具相关的异常都应继承此类。code 用于 Graph 做机器判断，
    retryable 标记该异常是否可以通过重试恢复。
    继承自 AppException 确保可以被全局异常处理器捕获。
    """

    def __init__(
        self,
        code: str = "TOOL_INTERNAL_ERROR",
        message: str = "Tool execution failed",
        detail: dict | None = None,
        retryable: bool = False,
    ):
        self.detail = detail or {}
        self.retryable = retryable
        # 先调用 AppException.__init__ 保证继承链完整，
        # 再覆盖 code 为字符串类型（Tool 领域使用字符串错误码，与 HTTP 整数错误码分离）
        super().__init__(code=0, message=message, http_status=500, data=None)
        self.code = code
        self.message = message


class ToolNotFoundError(ToolException):
    """按名称获取 Tool 时，目标 Tool 未注册。"""

    def __init__(self, tool_name: str):
        super().__init__(
            code="TOOL_NOT_FOUND",
            message=f"Tool not found: {tool_name}",
            detail={"tool_name": tool_name},
            retryable=False,
        )


class ToolValidationError(ToolException):
    """Tool 入参校验失败（非重试类异常）。"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(
            code="TOOL_VALIDATION_ERROR",
            message=message,
            detail=detail,
            retryable=False,
        )


class ToolTimeoutError(ToolException):
    """Tool 执行超时（可重试）。"""

    def __init__(self, message: str = "Tool execution timeout", detail: dict | None = None):
        super().__init__(
            code="TOOL_TIMEOUT",
            message=message,
            detail=detail,
            retryable=True,
        )


class ToolUpstreamError(ToolException):
    """上游服务异常（由调用方决定是否可重试）。"""

    def __init__(self, message: str, detail: dict | None = None, retryable: bool = False):
        super().__init__(
            code="TOOL_UPSTREAM_ERROR",
            message=message,
            detail=detail,
            retryable=retryable,
        )
