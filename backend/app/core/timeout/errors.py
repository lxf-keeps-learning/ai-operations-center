"""超时错误模型。

统一区分：
  - DeadlineExpiredError — Deadline 显式检查失败（内部协议）。
  - ReportTimeoutError  — 报告整体/Graph 超时 → HTTP 504 + 504102。
  - SseIdleTimeoutError — SSE 空闲超时 → HTTP 504 + 504103。
  - LLM 超时          — LlmResult.error_code == "LLM_TIMEOUT"（业务层）→ 504101。

CancelledError（用户主动取消）不属于本模块，始终原样向上传播。
"""

from typing import Any

from app.core.exception.base_exception import AppException
from app.core.exception.error_code import REPORT_TIMEOUT, SSE_IDLE_TIMEOUT


class DeadlineExpiredError(Exception):
    """Deadline 剩余预算耗尽（显式检查路径）。"""

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        elapsed_ms: int,
        remaining_ms: int = 0,
        retryable: bool = False,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.elapsed_ms = elapsed_ms
        self.remaining_ms = remaining_ms
        self.retryable = retryable
        self.detail = detail or {}
        super().__init__(f"{operation} 超时: {timeout_seconds}s")


class ReportTimeoutError(AppException):
    """报告生成整体超时（Graph 115s 或总预算 120s 内无法完成）。"""

    def __init__(
        self,
        message: str = "报告生成超时，请稍后重试",
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=REPORT_TIMEOUT.code,
            message=message,
            http_status=REPORT_TIMEOUT.http_status,
            data=detail,
        )


class SseIdleTimeoutError(AppException):
    """SSE 事件流空闲超时。"""

    def __init__(
        self,
        message: str = "事件流空闲超时",
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=SSE_IDLE_TIMEOUT.code,
            message=message,
            http_status=SSE_IDLE_TIMEOUT.http_status,
            data=detail,
        )
