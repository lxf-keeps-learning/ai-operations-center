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
        # 先调用 AppException.__init__ 保证继承链完整，
        # 再覆盖 code 为字符串类型（Tool 领域使用字符串错误码，与 HTTP 整数错误码分离）
        super().__init__(code=0, message=message, http_status=500, data=None)
        self.code = code
        self.message = message
        # AppException.__init__ 会写入默认 retryable，这里必须最后覆盖。
        self.retryable = retryable


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
    """Tool 执行超时（仅安全查询可重试）。"""

    def __init__(
        self,
        message: str = "Tool execution timeout",
        detail: dict | None = None,
        retryable: bool = True,
    ):
        super().__init__(
            code="TOOL_TIMEOUT",
            message=message,
            detail=detail,
            retryable=retryable,
        )


class WriteResultUnknownError(ToolException):
    """写操作超时后无法确认下游是否提交，结果状态为 result_unknown。

    不得自动重试；必须通过查询接口或补偿任务确认最终状态。
    """

    def __init__(
        self,
        message: str = "写操作超时，无法确认下游是否提交",
        detail: dict | None = None,
    ):
        super().__init__(
            code="WRITE_RESULT_UNKNOWN",
            message=message,
            detail=detail,
            retryable=False,
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


class CapabilityUnavailableError(ToolException):
    """能力不可用：工具不存在、已关闭或没有已发布版本，不暴露内部实现名。"""

    def __init__(self, capability: str | None = None):
        super().__init__(
            code="TOOL_CAPABILITY_UNAVAILABLE",
            message=(
                f"Capability unavailable: {capability}"
                if capability
                else "Capability unavailable"
            ),
            detail={"capability": capability} if capability else None,
            retryable=False,
        )


class ToolForbiddenError(ToolException):
    """权限拒绝：治理策略 deny 或非受信调用无匹配策略。"""

    def __init__(
        self,
        message: str = "Tool access denied by governance policy",
        detail: dict | None = None,
        *,
        resolution: dict | None = None,
    ):
        super().__init__(
            code="TOOL_FORBIDDEN",
            message=message,
            detail=detail,
            retryable=False,
        )
        # 仅供 Gateway 审计，不进入对调用方返回的 detail，避免泄露实现引用。
        self.resolution = resolution or {}


class ToolRateLimitedError(ToolException):
    """触发限流，携带下一窗口可重试秒数。"""

    def __init__(self, message: str = "Tool rate limit exceeded", retry_after_seconds: int | None = None):
        super().__init__(
            code="TOOL_RATE_LIMITED",
            message=message,
            detail=(
                {"retry_after_seconds": retry_after_seconds}
                if retry_after_seconds is not None
                else None
            ),
            retryable=True,
        )


class ConfirmationRequiredError(ToolException):
    """动作工具需要人工确认凭证后才能执行。"""

    def __init__(self, message: str = "Action requires human confirmation", detail: dict | None = None):
        super().__init__(
            code="TOOL_CONFIRMATION_REQUIRED",
            message=message,
            detail=detail,
            retryable=False,
        )


class RegistryConfigurationError(ToolException):
    """Registry 配置错误：执行器未绑定、Schema 非法、发布不变量被破坏等。"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(
            code="TOOL_REGISTRY_CONFIGURATION_ERROR",
            message=message,
            detail=detail,
            retryable=False,
        )


class RegistryUnavailableError(ToolException):
    """Registry 依赖（MySQL）不可用且缓存/快照无法继续服务。"""

    def __init__(self, message: str = "Tool registry temporarily unavailable", detail: dict | None = None):
        super().__init__(
            code="TOOL_REGISTRY_UNAVAILABLE",
            message=message,
            detail=detail,
            retryable=True,
        )
