from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ToolType(StrEnum):
    QUERY = "query"
    ANALYSIS = "analysis"
    ACTION = "action"


class ActionPhase(StrEnum):
    PREPARE = "prepare"
    COMMIT = "commit"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class GovernanceDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class ToolDefinitionRecord:
    id: int
    tool_key: str
    capability: str
    name: str
    description: str
    tool_type: ToolType
    action_phase: ActionPhase | None
    enabled: bool


@dataclass(frozen=True)
class ToolVersionRecord:
    id: int
    tool_id: int
    version: str
    implementation_ref: str
    input_schema: Mapping[str, object]
    output_schema: Mapping[str, object]
    status: VersionStatus
    is_stable: bool


@dataclass(frozen=True)
class ToolPolicyRecord:
    id: int
    tool_id: int
    version_id: int | None
    tenant_id: str | None
    role: str | None
    decision: GovernanceDecision
    rate_limit_per_minute: int
    gray_percentage: int
    requires_confirmation: bool
    enabled: bool


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: int
    tool_key: str
    capability: str
    name: str
    description: str
    tool_type: ToolType
    action_phase: ActionPhase | None
    version_id: int
    version: str
    input_schema: Mapping[str, object]
    output_schema: Mapping[str, object]
    rate_limit_per_minute: int
    selected_stable: bool


@dataclass(frozen=True)
class RegistrySnapshot:
    revision: str
    loaded_at: datetime
    definitions: tuple[ToolDefinitionRecord, ...]
    versions: tuple[ToolVersionRecord, ...]
    policies: tuple[ToolPolicyRecord, ...]


@dataclass(frozen=True)
class ResolvedTool:
    tool_id: int
    tool_key: str
    capability: str
    tool_type: ToolType
    action_phase: ActionPhase | None
    version_id: int
    version: str
    implementation_ref: str
    policy_id: int | None
    rate_limit_per_minute: int
    gray_bucket: int | None
    selected_stable: bool
    requires_confirmation: bool = False
