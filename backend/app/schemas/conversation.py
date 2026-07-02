from pydantic import Field

from app.schemas.common import IocBaseModel


class SessionSummary(IocBaseModel):
    session_id: str
    trace_id: str
    scene_code: str
    status: str
    message: str | None = None
    create_time: str


class ConversationSummary(IocBaseModel):
    conversation_id: str
    title: str
    agent_code: str
    update_time: str


class ConversationDetail(ConversationSummary):
    sessions: list[SessionSummary] = Field(default_factory=list)
