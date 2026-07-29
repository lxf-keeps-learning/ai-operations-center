from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode


PROMPT_NOT_FOUND = ErrorCode(code=404010, message="Prompt 不存在", http_status=404, description="指定的 Prompt 不存在")
VERSION_NOT_FOUND = ErrorCode(code=404011, message="Prompt 版本不存在", http_status=404, description="指定的 Prompt 版本不存在")
VARIABLE_NOT_FOUND = ErrorCode(code=404012, message="变量不存在", http_status=404, description="指定的变量不存在")
TEST_CASE_NOT_FOUND = ErrorCode(code=404013, message="测试用例不存在", http_status=404, description="指定的测试用例不存在")
RELEASE_NOT_FOUND = ErrorCode(code=404014, message="发布记录不存在", http_status=404, description="指定的发布记录不存在")
PROMPT_KEY_EXISTS = ErrorCode(code=400010, message="Prompt Key 已存在", http_status=400, description="指定的 Prompt Key 已存在")
PROMPT_KEY_INVALID = ErrorCode(code=400011, message="Prompt Key 格式无效", http_status=400, description="Prompt Key 只能包含小写字母、数字、点和下划线")
CANNOT_EDIT_PROTECTED = ErrorCode(code=403010, message="不可编辑受保护字段", http_status=403, description="运营人员不能修改系统层 Prompt 或安全约束")
CANNOT_DELETE_REQUIRED_RULE = ErrorCode(code=403011, message="不可删除必填规则", http_status=403, description="系统必填规则不可删除")
VERSION_LOCKED = ErrorCode(code=400012, message="版本已锁定", http_status=400, description="已发布版本不可修改，请复制为新草稿")
VARIABLE_MISSING = ErrorCode(code=400013, message="必填变量缺失", http_status=400, description="Prompt 渲染缺少必填变量")
INVALID_STATUS_TRANSITION = ErrorCode(code=400014, message="状态流转无效", http_status=400, description="当前状态不允许执行此操作")
PRODUCTION_DIRECT_READ = ErrorCode(code=400015, message="生产环境禁止直接读取草稿", http_status=400, description="生产环境只能使用已发布的版本")
NOT_APPROVED = ErrorCode(code=400016, message="版本未审核通过", http_status=400, description="只有审核通过的版本才能发布")
VERSION_ALREADY_RELEASED = ErrorCode(code=400017, message="版本已发布", http_status=400, description="该版本已发布到目标环境")
CANNOT_PUBLISH_DRAFT = ErrorCode(code=400018, message="草稿不可发布", http_status=400, description="草稿必须先提交审核")


def prompt_not_found(prompt_id: int | str) -> AppException:
    return AppException.from_error_code(PROMPT_NOT_FOUND, message=f"Prompt {prompt_id} 不存在")


def version_not_found(version_id: int | str) -> AppException:
    return AppException.from_error_code(VERSION_NOT_FOUND, message=f"Prompt 版本 {version_id} 不存在")


def variable_missing(key: str) -> AppException:
    return AppException.from_error_code(VARIABLE_MISSING, message=f"必填变量 '{key}' 缺失")


def invalid_status_transition(current: str, target: str) -> AppException:
    return AppException.from_error_code(
        INVALID_STATUS_TRANSITION,
        message=f"不允许从 {current} 状态流转到 {target} 状态",
    )
