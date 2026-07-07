class ToolException(Exception):
    def __init__(
        self,
        code: str = "TOOL_INTERNAL_ERROR",
        message: str = "Tool execution failed",
        detail: dict | None = None,
        retryable: bool = False,
    ):
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.retryable = retryable
        super().__init__(message)


class ToolNotFoundError(ToolException):
    def __init__(self, tool_name: str):
        super().__init__(
            code="TOOL_NOT_FOUND",
            message=f"Tool not found: {tool_name}",
            detail={"tool_name": tool_name},
            retryable=False,
        )


class ToolValidationError(ToolException):
    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(
            code="TOOL_VALIDATION_ERROR",
            message=message,
            detail=detail,
            retryable=False,
        )


class ToolTimeoutError(ToolException):
    def __init__(self, message: str = "Tool execution timeout", detail: dict | None = None):
        super().__init__(
            code="TOOL_TIMEOUT",
            message=message,
            detail=detail,
            retryable=True,
        )


class ToolUpstreamError(ToolException):
    def __init__(self, message: str, detail: dict | None = None, retryable: bool = False):
        super().__init__(
            code="TOOL_UPSTREAM_ERROR",
            message=message,
            detail=detail,
            retryable=retryable,
        )
