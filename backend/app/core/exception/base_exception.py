"""
应用异常基类 — 项目中所有业务异常的父类

包含 code（业务错误码）、message（错误描述）、http_status（HTTP 状态码）、data（附加数据）。
配合 exception_handler 统一转换为标准 ApiResponse 格式返回。
"""

from typing import Any

from app.core.exception.error_code import ErrorCode, INTERNAL_ERROR


class AppException(Exception):
    def __init__(
        self,
        code: int = INTERNAL_ERROR.code,
        message: str = INTERNAL_ERROR.message,
        http_status: int = INTERNAL_ERROR.http_status,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)

    @classmethod
    def from_error_code(cls, error_code: ErrorCode, message: str | None = None, data: Any = None) -> "AppException":
        """根据预定义的 ErrorCode 快速创建异常实例，可覆盖 message 和 data"""
        return cls(
            code=error_code.code,
            message=message or error_code.message,
            http_status=error_code.http_status,
            data=data,
        )

    def to_dict(self) -> dict[str, Any]:
        """转为字典格式，便于日志记录"""
        return {
            "code": self.code,
            "message": self.message,
            "http_status": self.http_status,
            "data": self.data,
        }
