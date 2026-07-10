"""
用户上下文 — 当前请求的用户身份信息

生命周期：单次 HTTP 请求。
包含：userId、username、orgId、角色列表、权限列表。
从请求头 X-User-Id / X-Username / X-Roles / X-Permissions 中解析。
"""

from dataclasses import dataclass, field


@dataclass
class UserContext:
    user_id: str = ""
    username: str = ""
    org_id: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转为驼峰命名字典，用于日志记录或接口展示"""
        return {
            "userId": self.user_id,
            "username": self.username,
            "orgId": self.org_id,
            "roles": self.roles,
            "permissions": self.permissions,
        }
