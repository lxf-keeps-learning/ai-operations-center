from app.schemas.common import IocBaseModel


class HealthStatus(IocBaseModel):
    status: str
    database: str
    redis: str
    llm: str
