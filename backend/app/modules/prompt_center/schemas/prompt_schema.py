from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import IocBaseModel


class VariableSchema(IocBaseModel):
    variable_key: str = Field(description="变量标识")
    variable_name: str = Field(description="变量名称")
    description: str | None = None
    data_type: str = "string"
    source_type: str = "graph_state"
    source_path: str | None = None
    required: bool = True
    default_value: str | None = None
    example_value: str | None = None
    sensitive: bool = False
    editable: bool = False
    display_order: int = 0


class PromptCreate(IocBaseModel):
    prompt_key: str = Field(description="Prompt 唯一标识，如 ioc.safety.analysis")
    prompt_name: str = Field(description="Prompt 名称")
    business_scene: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    description: str | None = None
    owner_id: str | None = None

    @field_validator("prompt_key")
    @classmethod
    def validate_prompt_key(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z][a-z0-9._-]{1,126}[a-z0-9]$", v):
            raise ValueError("Prompt Key 格式无效，只能包含小写字母、数字、点和下划线")
        return v


class PromptUpdate(IocBaseModel):
    prompt_name: str | None = None
    business_scene: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    description: str | None = None
    owner_id: str | None = None


class PromptResponse(IocBaseModel):
    id: int
    prompt_key: str
    prompt_name: str
    business_scene: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    description: str | None = None
    owner_id: str | None = None
    current_version_id: int | None = None
    status: str
    created_by: str | None = None
    created_at: datetime
    updated_by: str | None = None
    updated_at: datetime


class PromptDetailResponse(IocBaseModel):
    id: int
    prompt_key: str
    prompt_name: str
    business_scene: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    description: str | None = None
    owner_id: str | None = None
    current_version_id: int | None = None
    status: str
    created_by: str | None = None
    created_at: datetime
    updated_by: str | None = None
    updated_at: datetime
    variables: list[VariableSchema] = Field(default_factory=list)
    versions: list["PromptVersionSummary"] = Field(default_factory=list)


class PromptVersionSummary(IocBaseModel):
    id: int
    version: str
    status: str
    change_reason: str | None = None
    created_by: str | None = None
    created_at: datetime


class PromptMetricsResponse(IocBaseModel):
    prompt_id: int
    prompt_key: str
    compliance_rate: float | None = None
    format_compliance: float | None = None
    no_fabrication_rate: float | None = None
    evidence_complete_rate: float | None = None
    avg_tokens: int | None = None
    avg_latency_ms: float | None = None
    satisfaction_score: float | None = None
    total_runs: int = 0
    total_failures: int = 0
