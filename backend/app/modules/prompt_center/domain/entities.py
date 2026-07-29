from pydantic import Field

from app.schemas.common import IocBaseModel


class PromptRenderResult(IocBaseModel):
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


class RenderedPrompt(IocBaseModel):
    system_message: str
    business_message: str
    runtime_context: str
    user_message: str
    messages: list[dict]


class PromptValidationResult(IocBaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_variables: list[str] = Field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
