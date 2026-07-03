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
        return cls(
            code=error_code.code,
            message=message or error_code.message,
            http_status=error_code.http_status,
            data=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "http_status": self.http_status,
            "data": self.data,
        }
