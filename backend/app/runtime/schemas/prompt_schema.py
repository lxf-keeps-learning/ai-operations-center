"""
Prompt DTO — Prompt 模板的请求/响应数据结构

PromptCreate:  创建 Prompt 时的请求体
PromptStatusUpdate: 仅更新状态的请求体
PromptResponse: Prompt 的响应体（含版本号、内容、状态等）
"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class PromptCreate(IocBaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    variables: dict | None = None
    scene_code: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    created_by: str | None = Field(default=None, max_length=64)


class PromptStatusUpdate(IocBaseModel):
    status: str = Field(min_length=1)


class PromptResponse(IocBaseModel):
    id: str
    code: str
    name: str
    version: int
    content: str
    variables: dict | None
    scene_code: str | None
    status: str
    description: str | None
    created_by: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
