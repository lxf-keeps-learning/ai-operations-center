from dataclasses import dataclass, field


@dataclass
class UserContext:
    user_id: str = ""
    username: str = ""
    org_id: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "username": self.username,
            "orgId": self.org_id,
            "roles": self.roles,
            "permissions": self.permissions,
        }
