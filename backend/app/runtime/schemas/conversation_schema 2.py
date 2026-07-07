from datetime import datetime

from pydantic import Field

from app.runtime.schemas.status import CONV_ACTIVE, CONV_CREATED, CONV_STATUSES
from app.schemas.common import IocBaseModel


class ConversationCreate(IocBaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    biz_type: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=64)
    status: str = CONV_CREATED
    meta: dict | None = None


class ConversationUpdate(IocBaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = None


class ConversationStatusUpdate(IocBaseModel):
    status: str = Field(min_length=1)


class ConversationResponse(IocBaseModel):
    id: str
    user_id: str
    title: str | None
    biz_type: str | None
    source: str | None
    status: str
    meta: dict | None
    created_at: datetime
    updated_at: datetime
