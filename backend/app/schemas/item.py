from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class ItemCreate(IocBaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    is_active: bool = True


class ItemUpdate(IocBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    is_active: bool | None = None


class ItemResponse(IocBaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
