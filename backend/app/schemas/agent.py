from pydantic import Field

from app.schemas.common import BusinessContext, IocBaseModel, PageContext


class ChatRequest(IocBaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    agent_code: str = "operation"
    page_context: PageContext = Field(default_factory=PageContext)
    stream: bool = True


class AnalyzeRequest(IocBaseModel):
    agent_code: str = "operation"
    scene_code: str = "operation_daily_summary"
    message: str | None = "生成今日运营摘要"
    conversation_id: str | None = None
    page_context: PageContext = Field(default_factory=PageContext)
    business_context: BusinessContext | None = None
    stream: bool = True


class AgentTaskResponse(IocBaseModel):
    conversation_id: str
    session_id: str
    status: str = "running"
    stream_url: str


class StreamEvent(IocBaseModel):
    event: str
    trace_id: str = Field(alias="traceId")
    message: str | None = None
    content: str | None = None
    status: str | None = None
    code: int | None = None
    stage: str | None = None
