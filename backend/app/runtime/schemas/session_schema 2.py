from datetime import datetime

from pydantic import Field

from app.runtime.schemas.status import SESS_CREATED, SESS_STATUSES
from app.schemas.common import IocBaseModel


class SessionCreate(IocBaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    task_type: str | None = Field(default=None, max_length=64)
    input_text: str = Field(min_length=1)
    context: dict | None = None
    status: str = SESS_CREATED


class SessionUpdate(IocBaseModel):
    status: str | None = None
    output_text: str | None = None
    error_message: str | None = None


class SessionStatusUpdate(IocBaseModel):
    status: str = Field(min_length=1)


class SessionOutputUpdate(IocBaseModel):
    output_text: str | None = None


class SessionResponse(IocBaseModel):
    id: str
    conversation_id: str
    user_id: str
    task_type: str | None
    input_text: str
    context: dict | None
    output_text: str | None
    status: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    expire_at: datetime | None
    created_at: datetime
    updated_at: datetime
