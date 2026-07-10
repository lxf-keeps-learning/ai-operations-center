"""
Feedback DTO — 用户反馈的请求/响应数据结构

FeedbackCreate:  提交反馈时的请求体（评分 1-5、反馈类型、文字内容）
FeedbackResponse: 反馈的响应体
"""

from datetime import datetime

from pydantic import Field

from app.runtime.schemas.status import FB_OTHER, FB_TYPES
from app.schemas.common import IocBaseModel


class FeedbackCreate(IocBaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback_type: str | None = Field(default=None, max_length=64)
    content: str | None = None


class FeedbackResponse(IocBaseModel):
    id: str
    conversation_id: str
    session_id: str
    user_id: str
    rating: int | None
    feedback_type: str | None
    content: str | None
    created_at: datetime
