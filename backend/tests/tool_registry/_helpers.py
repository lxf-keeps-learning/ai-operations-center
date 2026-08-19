from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.tool_center.base_tool import BaseTool
from app.tool_registry.confirmation import ConfirmationService
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
from app.tool_registry.executor_catalog import ExecutorCatalog
from app.tool_registry.gateway import ToolGateway
from app.tool_registry.models import ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.rate_limit import InMemoryFixedWindowRateLimiter, RateLimiter
from app.tool_registry.registry import DatabaseToolRegistry
from app.tool_registry.repository import ToolRegistryRepository


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


def _enable_foreign_keys(dbapi_connection: sqlite3.Connection, _record: object) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def make_sqlite_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def build_gateway(
    definitions: Sequence[ToolDefinitionRecord],
    versions: Sequence[ToolVersionRecord],
    policies: Sequence[ToolPolicyRecord],
    *,
    executors: dict[str, BaseTool],
    rate_limiter: RateLimiter | None = None,
    session_factory: sessionmaker | None = None,
    repository_factory=None,
    confirmation_secret: str = "unit-test-secret",
    clock: FakeClock | None = None,
) -> tuple[ToolGateway, SnapshotLoader, sessionmaker | None]:
    clock = clock or FakeClock()
    loader = SnapshotLoader(definitions, versions, policies, clock=clock)
    registry = DatabaseToolRegistry(
        loader,
        cache_ttl_seconds=30,
        stale_query_ttl_seconds=86400,
        clock=clock,
    )
    session_factory = session_factory or make_sqlite_session_factory()
    _seed_registry_rows(session_factory, definitions, versions, policies)
    if repository_factory is None:
        repository_factory = lambda: ToolRegistryRepository(session_factory())
    catalog = ExecutorCatalog()
    for ref, tool in executors.items():
        catalog.register(ref, tool)
    gateway = ToolGateway(
        registry=registry,
        executors=catalog,
        rate_limiter=rate_limiter or InMemoryFixedWindowRateLimiter(),
        repository_factory=repository_factory,
        confirmation_service=ConfirmationService(secret=confirmation_secret, ttl_seconds=300),
        clock=clock,
    )
    return gateway, loader, session_factory


def _seed_registry_rows(
    session_factory: sessionmaker,
    definitions: Sequence[ToolDefinitionRecord],
    versions: Sequence[ToolVersionRecord],
    policies: Sequence[ToolPolicyRecord],
) -> None:
    with session_factory() as session:
        for definition in definitions:
            session.add(
                ToolDefinition(
                    id=definition.id,
                    tool_key=definition.tool_key,
                    capability=definition.capability,
                    name=definition.name,
                    description=definition.description,
                    tool_type=definition.tool_type.value,
                    action_phase=(
                        definition.action_phase.value if definition.action_phase else None
                    ),
                    enabled=definition.enabled,
                )
            )
        for version in versions:
            session.add(
                ToolVersion(
                    id=version.id,
                    tool_id=version.tool_id,
                    version=version.version,
                    implementation_ref=version.implementation_ref,
                    input_schema=dict(version.input_schema),
                    output_schema=dict(version.output_schema),
                    status=version.status.value,
                    is_stable=version.is_stable,
                )
            )
        for policy in policies:
            session.add(
                ToolPolicy(
                    id=policy.id,
                    tool_id=policy.tool_id,
                    version_id=policy.version_id,
                    tenant_id=policy.tenant_id,
                    role=policy.role,
                    decision=policy.decision.value,
                    rate_limit_per_minute=policy.rate_limit_per_minute,
                    gray_percentage=policy.gray_percentage,
                    requires_confirmation=policy.requires_confirmation,
                    enabled=policy.enabled,
                )
            )
        session.commit()
