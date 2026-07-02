from pydantic import Field

from app.schemas.common import IocBaseModel


class FeedbackRequest(IocBaseModel):
    conversation_id: str | None = None
    session_id: str | None = None
    trace_id: str = Field(alias="trace_id")
    score: int | None = Field(default=None, ge=1, le=5)
    attitude: str | None = None
    comment: str | None = None


class FeedbackResponse(IocBaseModel):
    feedback_id: str
