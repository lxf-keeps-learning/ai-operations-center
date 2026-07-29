from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode


EVALUATION_NOT_FOUND = ErrorCode(code=404020, message="评估结果不存在", http_status=404, description="指定的评估记录不存在")
EVALUATION_RESULT_FAILED = ErrorCode(code=500020, message="评估执行失败", http_status=500, description="评估器执行异常")
INVALID_EVALUATOR = ErrorCode(code=400020, message="评估器不存在", http_status=400, description="指定的评估器未注册")


def evaluation_not_found(result_id: int) -> AppException:
    return AppException.from_error_code(EVALUATION_NOT_FOUND, message=f"评估记录 {result_id} 不存在")


def invalid_evaluator(key: str) -> AppException:
    return AppException.from_error_code(INVALID_EVALUATOR, message=f"评估器 {key} 未注册")
