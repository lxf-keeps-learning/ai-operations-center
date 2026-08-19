from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCreateRequest(BaseModel):
    tool_key: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    tool_type: Literal["query", "analysis", "action"]
    action_phase: Literal["prepare", "commit"] | None = None
    enabled: bool = True


class ToolUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    enabled: bool | None = None


class VersionCreateRequest(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    implementation_ref: str = Field(min_length=1, max_length=255)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class PublishRequest(BaseModel):
    release_type: Literal["stable", "gray"] = "stable"
    gray_percentage: int = Field(default=0, ge=0, le=100)


class PolicySpec(BaseModel):
    version: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    decision: Literal["allow", "deny"] = "allow"
    rate_limit_per_minute: int = Field(default=60, ge=1)
    gray_percentage: int = Field(default=0, ge=0, le=100)
    requires_confirmation: bool = False
    enabled: bool = True


class PolicyReplaceRequest(BaseModel):
    policies: list[PolicySpec]


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tool_key: str
    capability: str
    name: str
    description: str
    tool_type: str
    action_phase: str | None
    enabled: bool


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tool_id: int
    version: str
    implementation_ref: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    status: str
    is_stable: bool
    published_at: datetime | None
    published_by: str | None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tool_id: int
    version_id: int | None
    tenant_id: str | None
    role: str | None
    decision: str
    rate_limit_per_minute: int
    gray_percentage: int
    requires_confirmation: bool
    enabled: bool


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trace_id: str
    tool_id: int | None
    version_id: int | None
    implementation_ref: str | None
    tenant_id: str | None
    user_id: str | None
    role: str | None
    caller_type: str
    policy_id: int | None
    decision: str
    gray_bucket: int | None
    selected_stable: bool | None
    status: str
    duration_ms: int | None
    error_code: str | None
    argument_hash: str
    argument_summary: dict[str, Any] | None
    created_at: datetime


class AuditPageResponse(BaseModel):
    items: list[AuditResponse]
    total: int
    offset: int
    limit: int
