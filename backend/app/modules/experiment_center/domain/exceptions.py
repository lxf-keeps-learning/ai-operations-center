from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode

EXPERIMENT_NOT_FOUND = ErrorCode(code=404030, message="实验不存在", http_status=404, description="指定的实验不存在")
EXPERIMENT_RESULT_NOT_FOUND = ErrorCode(code=404031, message="实验结果不存在", http_status=404, description="指定的实验结果不存在")
EXPERIMENT_ALREADY_RUNNING = ErrorCode(code=400030, message="实验正在运行中", http_status=400, description="实验正在执行，不能重复触发")
INVALID_VERSION_PAIR = ErrorCode(code=400031, message="版本必须属于同一个 Prompt", http_status=400, description="两个版本必须属于同一个 Prompt 定义")


def experiment_not_found(exp_id: int):
    return AppException.from_error_code(EXPERIMENT_NOT_FOUND, message=f"实验 {exp_id} 不存在")


def invalid_version_pair():
    return AppException.from_error_code(INVALID_VERSION_PAIR)
