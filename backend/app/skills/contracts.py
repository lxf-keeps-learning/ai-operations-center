"""Runtime Skill 契约。"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillRiskLevel(StrEnum):
    """Skill 对外部业务系统的风险等级。"""

    READ_ONLY = "read_only"
    HUMAN_CONFIRMATION = "human_confirmation"
    RESTRICTED = "restricted"


class SkillSideEffects(BaseModel):
    """Skill 执行时允许的副作用。"""

    business_write: bool = Field(
        default=False,
        description="是否修改 IOC/ERP/工单等外部业务系统",
    )
    runtime_persistence: bool = Field(
        default=True,
        description="是否允许保存分析报告、会话消息和审计记录",
    )


class SkillDefinition(BaseModel):
    """Skill 可发现元数据，不承担 Graph 执行逻辑。"""

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    description: str
    version: str = "1.0.0"
    executor_type: Literal["graph"] = "graph"
    executor_id: str
    required_inputs: list[str] = Field(default_factory=list)
    optional_inputs: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    risk_level: SkillRiskLevel = SkillRiskLevel.READ_ONLY
    side_effects: SkillSideEffects = Field(default_factory=SkillSideEffects)
    tags: list[str] = Field(default_factory=list)


class SkillExecutionRequest(BaseModel):
    """Skill 统一执行请求。"""

    inputs: dict[str, Any] = Field(default_factory=dict)


class SkillExecutionContext(BaseModel):
    """API 边界注入的身份与链路上下文。"""

    trace_id: str | None = None
    user_id: str = "anonymous"
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class SkillExecutionResult(BaseModel):
    """Skill 统一执行结果。"""

    skill_id: str
    skill_version: str
    trace_id: str
    status: Literal["success", "partial", "failed"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
