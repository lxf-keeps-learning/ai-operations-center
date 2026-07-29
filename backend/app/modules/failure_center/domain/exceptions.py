from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode

FAILURE_NOT_FOUND = ErrorCode(code=404040, message="失败案例不存在", http_status=404, description="指定的失败案例不存在")


def failure_not_found(failure_id: int) -> AppException:
    return AppException.from_error_code(FAILURE_NOT_FOUND, message=f"失败案例 {failure_id} 不存在")
