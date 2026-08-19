from app.core.context.context_holder import get_user_context
from app.core.context.user_context import UserContext
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import FORBIDDEN


def require_tool_registry_admin() -> UserContext:
    """仅允许 admin 角色访问工具注册中心管理接口。"""
    user = get_user_context()
    if "admin" not in user.roles:
        raise AppException.from_error_code(FORBIDDEN)
    return user
