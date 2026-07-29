from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel

# model_config is reserved by Pydantic v2; use _config for model configuration dict
MODEL_CONFIG_FIELD = "model_config"


class RuleItem(IocBaseModel):
    key: str = Field(description="规则标识")
    content: str = Field(description="规则内容")
    enabled: bool = True
    required: bool = False
    display_order: int = 0


class ExampleItem(IocBaseModel):
    title: str = Field(description="示例标题")
    content: str = Field(description="示例内容")
    description: str | None = None


class VersionCreate(IocBaseModel):
    system_content: str | None = None
    business_role_content: str | None = None
    business_goal_content: str | None = None
    business_rules: list[RuleItem] | None = None
    output_requirement: str | None = None
    positive_examples: list[ExampleItem] | None = None
    negative_examples: list[ExampleItem] | None = None
    llm_config: dict | None = Field(default=None, alias="model_config")
    output_schema: dict | None = None
    change_reason: str | None = Field(default=None, max_length=500)
    created_by: str | None = None


class VersionUpdate(IocBaseModel):
    system_content: str | None = None
    business_role_content: str | None = None
    business_goal_content: str | None = None
    business_rules: list[RuleItem] | None = None
    output_requirement: str | None = None
    positive_examples: list[ExampleItem] | None = None
    negative_examples: list[ExampleItem] | None = None
    llm_config: dict | None = Field(default=None, alias="model_config")
    output_schema: dict | None = None
    change_reason: str | None = Field(default=None, max_length=500)


class VersionResponse(IocBaseModel):
    id: int
    prompt_id: int
    version: str
    system_content: str | None = None
    business_role_content: str | None = None
    business_goal_content: str | None = None
    business_rules: list | None = None
    output_requirement: str | None = None
    positive_examples: list | None = None
    negative_examples: list | None = None
    llm_config: dict | None = Field(default=None, alias="model_config")
    output_schema: dict | None = None
    langsmith_commit_hash: str | None = None
    langsmith_tag: str | None = None
    status: str
    change_reason: str | None = None
    created_by: str | None = None
    created_at: datetime


class VersionCompareResponse(IocBaseModel):
    source_version: VersionResponse
    target_version: VersionResponse
    diffs: list["DiffItem"] = Field(default_factory=list)


class DiffItem(IocBaseModel):
    field: str = Field(description="差异字段")
    field_label: str = Field(description="差异字段中文名")
    source_value: str | None = None
    target_value: str | None = None
    change_type: str = Field(description="modified/added/removed/unchanged")


class ReviewerAction(IocBaseModel):
    comment: str | None = Field(default=None, max_length=500)
    operator_id: str | None = None
    operator_name: str | None = None
