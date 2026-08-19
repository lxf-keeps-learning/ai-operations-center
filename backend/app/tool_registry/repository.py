from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tool_registry.contracts import (
    ActionPhase,
    GovernanceDecision,
    RegistrySnapshot,
    ToolDefinitionRecord,
    ToolPolicyRecord,
    ToolType,
    ToolVersionRecord,
    VersionStatus,
)
from app.tool_registry.models import ToolCallAudit, ToolDefinition, ToolPolicy, ToolVersion


@dataclass(frozen=True)
class AuditFilters:
    trace_id: str | None = None
    tool_id: int | None = None
    version_id: int | None = None
    policy_id: int | None = None
    implementation_ref: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    role: str | None = None
    decision: str | None = None
    status: str | None = None


class FrozenDict(dict[str, object]):
    def __delitem__(self, key: str) -> None:
        raise TypeError("frozen schema mappings are immutable")

    def __ior__(self, other: object) -> "FrozenDict":
        raise TypeError("frozen schema mappings are immutable")

    def __setitem__(self, key: str, value: object) -> None:
        raise TypeError("frozen schema mappings are immutable")

    def clear(self) -> None:
        raise TypeError("frozen schema mappings are immutable")

    def pop(self, key: str, default: object = None) -> object:
        raise TypeError("frozen schema mappings are immutable")

    def popitem(self) -> tuple[str, object]:
        raise TypeError("frozen schema mappings are immutable")

    def setdefault(self, key: str, default: object = None) -> object:
        raise TypeError("frozen schema mappings are immutable")

    def update(self, *args: object, **kwargs: object) -> None:
        raise TypeError("frozen schema mappings are immutable")


class FrozenList(list[object]):
    def __delitem__(self, index: int | slice) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def __iadd__(self, other: object) -> "FrozenList":
        raise TypeError("frozen schema arrays are immutable")

    def __imul__(self, other: object) -> "FrozenList":
        raise TypeError("frozen schema arrays are immutable")

    def __setitem__(self, index: int | slice, value: object) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def append(self, value: object) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def clear(self) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def extend(self, values: object) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def insert(self, index: int, value: object) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def pop(self, index: int = -1) -> object:
        raise TypeError("frozen schema arrays are immutable")

    def remove(self, value: object) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def reverse(self) -> None:
        raise TypeError("frozen schema arrays are immutable")

    def sort(self, *args: object, **kwargs: object) -> None:
        raise TypeError("frozen schema arrays are immutable")


class ToolRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_definition(self, tool_key: str, *, for_update: bool = False) -> ToolDefinition | None:
        statement = select(ToolDefinition).where(ToolDefinition.tool_key == tool_key)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_definitions(self) -> list[ToolDefinition]:
        return list(self.db.scalars(select(ToolDefinition).order_by(ToolDefinition.id)))

    def save_definition(self, definition: ToolDefinition) -> ToolDefinition:
        self.db.add(definition)
        self.db.flush()
        return definition

    def get_version(self, tool_id: int, version: str) -> ToolVersion | None:
        return self.db.scalar(
            select(ToolVersion)
            .where(ToolVersion.tool_id == tool_id, ToolVersion.version == version)
        )

    def list_versions(self, tool_id: int) -> list[ToolVersion]:
        return list(
            self.db.scalars(
                select(ToolVersion)
                .where(ToolVersion.tool_id == tool_id)
                .order_by(ToolVersion.id)
            )
        )

    def save_version(self, version: ToolVersion) -> ToolVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_policy(
        self,
        tool_id: int,
        *,
        version_id: int | None,
        tenant_id: str | None,
        role: str | None,
    ) -> ToolPolicy | None:
        return self.db.scalar(
            select(ToolPolicy).where(
                ToolPolicy.tool_id == tool_id,
                ToolPolicy.version_id.is_(version_id) if version_id is None else ToolPolicy.version_id == version_id,
                ToolPolicy.tenant_id.is_(tenant_id) if tenant_id is None else ToolPolicy.tenant_id == tenant_id,
                ToolPolicy.role.is_(role) if role is None else ToolPolicy.role == role,
            )
        )

    def list_policies(self, tool_id: int) -> list[ToolPolicy]:
        return list(
            self.db.scalars(
                select(ToolPolicy)
                .where(ToolPolicy.tool_id == tool_id)
                .order_by(ToolPolicy.id)
            )
        )

    def save_policy(self, policy: ToolPolicy) -> ToolPolicy:
        self.db.add(policy)
        self.db.flush()
        return policy

    def load_snapshot(self) -> RegistrySnapshot:
        definitions = list(
            self.db.scalars(
                select(ToolDefinition)
                .where(ToolDefinition.enabled.is_(True))
                .order_by(ToolDefinition.id)
            )
        )
        tool_ids = [definition.id for definition in definitions]

        versions = list(
            self.db.scalars(
                select(ToolVersion)
                .where(
                    ToolVersion.tool_id.in_(tool_ids),
                    ToolVersion.status == VersionStatus.PUBLISHED.value,
                )
                .order_by(ToolVersion.id)
            )
        ) if tool_ids else []
        published_version_ids = [version.id for version in versions]

        policies = list(
            self.db.scalars(
                select(ToolPolicy)
                .where(
                    ToolPolicy.tool_id.in_(tool_ids),
                    ToolPolicy.enabled.is_(True),
                    ToolPolicy.version_id.is_(None) | ToolPolicy.version_id.in_(published_version_ids),
                )
                .order_by(ToolPolicy.id)
            )
        ) if tool_ids else []

        definition_records = tuple(self._to_definition_record(definition) for definition in definitions)
        version_records = tuple(self._to_version_record(version) for version in versions)
        policy_records = tuple(self._to_policy_record(policy) for policy in policies)
        loaded_at = datetime.now(UTC)

        return RegistrySnapshot(
            revision=f"{loaded_at.isoformat()}:{len(definition_records)}:{len(version_records)}:{len(policy_records)}",
            loaded_at=loaded_at,
            definitions=definition_records,
            versions=version_records,
            policies=policy_records,
        )

    def list_audits(
        self,
        filters: AuditFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[ToolCallAudit], int]:
        conditions = []
        if filters.trace_id is not None:
            conditions.append(ToolCallAudit.trace_id == filters.trace_id)
        if filters.tool_id is not None:
            conditions.append(ToolCallAudit.tool_id == filters.tool_id)
        if filters.version_id is not None:
            conditions.append(ToolCallAudit.version_id == filters.version_id)
        if filters.policy_id is not None:
            conditions.append(ToolCallAudit.policy_id == filters.policy_id)
        if filters.implementation_ref is not None:
            conditions.append(ToolCallAudit.implementation_ref == filters.implementation_ref)
        if filters.tenant_id is not None:
            conditions.append(ToolCallAudit.tenant_id == filters.tenant_id)
        if filters.user_id is not None:
            conditions.append(ToolCallAudit.user_id == filters.user_id)
        if filters.role is not None:
            conditions.append(ToolCallAudit.role == filters.role)
        if filters.decision is not None:
            conditions.append(ToolCallAudit.decision == filters.decision)
        if filters.status is not None:
            conditions.append(ToolCallAudit.status == filters.status)

        total = self.db.scalar(
            select(func.count())
            .select_from(ToolCallAudit)
            .where(*conditions)
        ) or 0
        rows = list(
            self.db.scalars(
                select(ToolCallAudit)
                .where(*conditions)
                .order_by(ToolCallAudit.created_at.desc(), ToolCallAudit.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return rows, total

    def append_audit(self, audit: ToolCallAudit) -> ToolCallAudit:
        self.db.add(audit)
        self.db.flush()
        return audit

    def update_audit(
        self,
        audit_id: int,
        *,
        status: str,
        duration_ms: int,
        error_code: str | None,
    ) -> None:
        audit = self.db.get(ToolCallAudit, audit_id)
        if audit is None:
            raise LookupError(f"tool audit {audit_id} not found")
        audit.status = status
        audit.duration_ms = duration_ms
        audit.error_code = error_code
        self.db.flush()

    def _to_definition_record(self, definition: ToolDefinition) -> ToolDefinitionRecord:
        return ToolDefinitionRecord(
            id=definition.id,
            tool_key=definition.tool_key,
            capability=definition.capability,
            name=definition.name,
            description=definition.description,
            tool_type=ToolType(definition.tool_type),
            action_phase=ActionPhase(definition.action_phase) if definition.action_phase else None,
            enabled=definition.enabled,
        )

    def _to_version_record(self, version: ToolVersion) -> ToolVersionRecord:
        return ToolVersionRecord(
            id=version.id,
            tool_id=version.tool_id,
            version=version.version,
            implementation_ref=version.implementation_ref,
            input_schema=_freeze_json_mapping(version.input_schema),
            output_schema=_freeze_json_mapping(version.output_schema),
            status=VersionStatus(version.status),
            is_stable=version.is_stable,
        )

    def _to_policy_record(self, policy: ToolPolicy) -> ToolPolicyRecord:
        return ToolPolicyRecord(
            id=policy.id,
            tool_id=policy.tool_id,
            version_id=policy.version_id,
            tenant_id=policy.tenant_id,
            role=policy.role,
            decision=GovernanceDecision(policy.decision),
            rate_limit_per_minute=policy.rate_limit_per_minute,
            gray_percentage=policy.gray_percentage,
            requires_confirmation=policy.requires_confirmation,
            enabled=policy.enabled,
        )


def _freeze_json_mapping(value: Mapping[str, Any]) -> Mapping[str, object]:
    frozen = _freeze_json_value(dict(value))
    return cast(Mapping[str, object], frozen)


def _freeze_json_value(value: Any) -> object:
    if isinstance(value, Mapping):
        return FrozenDict(
            {str(key): _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return FrozenList(_freeze_json_value(item) for item in value)
    return value
