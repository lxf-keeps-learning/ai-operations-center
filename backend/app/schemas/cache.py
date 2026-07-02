from app.schemas.common import IocBaseModel


class CachePingResponse(IocBaseModel):
    enabled: bool
    status: str
    message: str
    response: str | None = None
    error: str | None = None
