from datetime import datetime

from app.schemas.common import IocBaseModel


class OverviewMetrics(IocBaseModel):
    today_requests: int
    running_tasks: int
    pending_messages: int
    failed_tasks: int
    total_tokens: int
    agent_success_rate: float
    average_response_ms: float


class OverviewSession(IocBaseModel):
    id: str
    conversation_id: str
    title: str
    agent: str
    channel: str
    runs: int
    total_tokens: int
    status: str
    updated_at: datetime


class PlatformOverviewResponse(IocBaseModel):
    metrics: OverviewMetrics
    recent_sessions: list[OverviewSession]
