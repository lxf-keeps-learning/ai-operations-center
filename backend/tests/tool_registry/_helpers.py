from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

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


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 8, 19, 10, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now = self._now + timedelta(seconds=seconds)


def make_definition(
    tool_id: int,
    tool_key: str,
    capability: str,
    name: str = "",
    description: str = "",
    tool_type: ToolType = ToolType.QUERY,
    action_phase: ActionPhase | None = None,
    enabled: bool = True,
) -> ToolDefinitionRecord:
    return ToolDefinitionRecord(
        id=tool_id,
        tool_key=tool_key,
        capability=capability,
        name=name or tool_key,
        description=description or f"description for {tool_key}",
        tool_type=tool_type,
        action_phase=action_phase,
        enabled=enabled,
    )


def make_version(
    version_id: int,
    tool_id: int,
    *,
    version: str = "1.0.0",
    implementation_ref: str = "",
    is_stable: bool = True,
    status: VersionStatus = VersionStatus.PUBLISHED,
) -> ToolVersionRecord:
    return ToolVersionRecord(
        id=version_id,
        tool_id=tool_id,
        version=version,
        implementation_ref=implementation_ref or f"builtin.tool_{version_id}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status=status,
        is_stable=is_stable,
    )


def make_policy(
    policy_id: int,
    tool_id: int,
    *,
    version_id: int | None = None,
    tenant_id: str | None = None,
    role: str | None = None,
    decision: GovernanceDecision = GovernanceDecision.ALLOW,
    rate_limit_per_minute: int = 60,
    gray_percentage: int = 0,
    requires_confirmation: bool = False,
    enabled: bool = True,
) -> ToolPolicyRecord:
    return ToolPolicyRecord(
        id=policy_id,
        tool_id=tool_id,
        version_id=version_id,
        tenant_id=tenant_id,
        role=role,
        decision=decision,
        rate_limit_per_minute=rate_limit_per_minute,
        gray_percentage=gray_percentage,
        requires_confirmation=requires_confirmation,
        enabled=enabled,
    )


class SnapshotLoader:
    def __init__(
        self,
        definitions: Sequence[ToolDefinitionRecord] = (),
        versions: Sequence[ToolVersionRecord] = (),
        policies: Sequence[ToolPolicyRecord] = (),
        loaded_at: datetime | None = None,
        clock: FakeClock | None = None,
    ) -> None:
        self.definitions = list(definitions)
        self.versions = list(versions)
        self.policies = list(policies)
        self.loaded_at = loaded_at
        self.clock = clock
        self.failing = False
        self.calls = 0

    def __call__(self) -> RegistrySnapshot:
        self.calls += 1
        if self.failing:
            raise OSError("database unavailable")
        return RegistrySnapshot(
            revision=f"r{self.calls}",
            loaded_at=(
                self.loaded_at
                if self.loaded_at is not None
                else (self.clock.now() if self.clock is not None else datetime(2026, 8, 19, 9, 0, 0, tzinfo=UTC))
            ),
            definitions=tuple(self.definitions),
            versions=tuple(self.versions),
            policies=tuple(self.policies),
        )
