from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class ReleaseRequest(IocBaseModel):
    environment: str = Field(description="发布环境")
    release_type: str = "full"
    traffic_ratio: int | None = Field(default=None, ge=1, le=100, description="灰度比例 1-100")
    release_note: str | None = None
    approved_by: str | None = None
    released_by: str | None = None


class ReleaseResponse(IocBaseModel):
    id: int
    prompt_id: int
    version_id: int
    environment: str
    release_type: str
    traffic_ratio: int | None = None
    status: str
    approved_by: str | None = None
    released_by: str | None = None
    released_at: datetime
    rollback_version_id: int | None = None
    release_note: str | None = None


class RollbackRequest(IocBaseModel):
    environment: str = Field(description="回滚环境")
    released_by: str | None = None
    release_note: str | None = None


class RenderRequest(IocBaseModel):
    prompt_key: str = Field(description="Prompt Key")
    environment: str = "development"
    version: str | None = None
    variables: dict = Field(default_factory=dict, description="运行时变量")
    user_question: str | None = None


class PreviewRequest(IocBaseModel):
    prompt_id: int
    version_id: int
    variables: dict = Field(default_factory=dict)
    user_question: str | None = None


class RenderResponse(IocBaseModel):
    prompt_id: int
    prompt_key: str
    prompt_name: str
    version: str
    environment: str
    messages: list[dict]
    variables: dict
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    output_schema: dict | None = None
    langsmith_commit_hash: str | None = None
    langsmith_tag: str | None = None
