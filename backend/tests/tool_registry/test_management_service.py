from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_center.exceptions import (
    RegistryConfigurationError,
    ToolForbiddenError,
    ToolNotFoundError,
)
from app.tool_registry.executor_catalog import ExecutorCatalog
from app.tool_registry.models import ToolCallAudit, ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.registry import DatabaseToolRegistry
from app.tool_registry.schemas import (
    PolicySpec,
    ToolCreateRequest,
    ToolUpdateRequest,
    VersionCreateRequest,
)
from app.tool_registry.service import ToolRegistryService

from tests.tool_registry._helpers import make_sqlite_session_factory


class StubTool(BaseTool):
    name = "stub"
    description = "stub"

    async def _execute(self, tool_input: BaseToolInput):
        return {}, [], {}


@pytest.fixture
def db() -> Iterator[Session]:
    session_factory = make_sqlite_session_factory()
    with session_factory() as session:
        yield session


@pytest.fixture
def invalidation_calls() -> list[str]:
    return []


@pytest.fixture
def service(db: Session, invalidation_calls: list[str]) -> ToolRegistryService:
    executors = ExecutorCatalog()
    executors.register("builtin.stub", StubTool())
    return ToolRegistryService(
        db,
        executors=executors,
        on_config_changed=lambda: invalidation_calls.append("invalidated"),
    )


def _create_query_tool(service: ToolRegistryService, tool_key: str) -> None:
    service.create_tool(
        ToolCreateRequest(
            tool_key=tool_key,
            capability=f"query.{tool_key}",
            name=tool_key,
            description="test tool",
            tool_type="query",
        ),
        operator_id="admin",
    )


def _create_version(
    service: ToolRegistryService,
    tool_key: str,
    version: str,
    implementation_ref: str = "builtin.stub",
) -> None:
    service.create_version(
        tool_key,
        VersionCreateRequest(
            version=version,
            implementation_ref=implementation_ref,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        ),
        operator_id="admin",
    )


def _tool_orm(db: Session, tool_key: str) -> ToolDefinition | None:
    return db.scalar(select(ToolDefinition).where(ToolDefinition.tool_key == tool_key))


def _version_orm(db: Session, tool_key: str, version: str) -> ToolVersion | None:
    tool = _tool_orm(db, tool_key)
    if tool is None:
        return None
    return db.scalar(
        select(ToolVersion).where(ToolVersion.tool_id == tool.id, ToolVersion.version == version)
    )


def test_create_tool_persists_definition(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "kpi_query")

    stored = _tool_orm(db, "kpi_query")
    assert stored is not None
    assert stored.capability == "query.kpi_query"
    assert stored.enabled is True


def test_create_tool_rejects_duplicate_key(service: ToolRegistryService) -> None:
    _create_query_tool(service, "dup_tool")

    with pytest.raises(RegistryConfigurationError, match="tool_key"):
        _create_query_tool(service, "dup_tool")


def test_create_tool_rejects_duplicate_capability(service: ToolRegistryService) -> None:
    _create_query_tool(service, "first_tool")

    with pytest.raises(RegistryConfigurationError, match="capability"):
        service.create_tool(
            ToolCreateRequest(
                tool_key="second_tool",
                capability="query.first_tool",
                name="second",
                description="second",
                tool_type="query",
            ),
            operator_id="admin",
        )


def test_create_tool_maps_concurrent_unique_conflict(
    service: ToolRegistryService,
    monkeypatch,
) -> None:
    def raise_unique(_definition):
        raise IntegrityError(
            "INSERT",
            {},
            RuntimeError("UNIQUE constraint failed: tool_definitions.capability"),
        )

    monkeypatch.setattr(service.repository, "save_definition", raise_unique)

    with pytest.raises(RegistryConfigurationError, match="capability"):
        _create_query_tool(service, "race_tool")


def test_create_version_defaults_to_draft(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.0.0")

    stored = _version_orm(db, "new_tool", "1.0.0")
    assert stored is not None
    assert stored.status == "draft"
    assert stored.is_stable is False


def test_create_version_validates_schema(service: ToolRegistryService) -> None:
    _create_query_tool(service, "schema_tool")

    with pytest.raises(RegistryConfigurationError, match="schema"):
        service.create_version(
            "schema_tool",
            VersionCreateRequest(
                version="1.0.0",
                implementation_ref="builtin.stub",
                input_schema={"type": "not-a-type"},
                output_schema={"type": "object"},
            ),
            operator_id="admin",
        )


def test_create_version_maps_concurrent_unique_conflict(
    service: ToolRegistryService,
    monkeypatch,
) -> None:
    _create_query_tool(service, "version_race")
    monkeypatch.setattr(service.repository, "get_version", lambda *_args: None)

    def raise_unique(_version):
        raise IntegrityError(
            "INSERT",
            {},
            RuntimeError("UNIQUE constraint failed: tool_versions.tool_id, tool_versions.version"),
        )

    monkeypatch.setattr(service.repository, "save_version", raise_unique)

    with pytest.raises(RegistryConfigurationError, match="version"):
        _create_version(service, "version_race", "1.0.0")


def test_publish_rejects_unbound_executor(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.0.0", implementation_ref="builtin.unbound")

    with pytest.raises(RegistryConfigurationError, match="implementation_ref"):
        service.publish_version("new_tool", "1.0.0", release_type="stable", operator_id="admin")

    stored = _version_orm(db, "new_tool", "1.0.0")
    assert stored is not None
    assert stored.status == "draft"


def test_publish_gray_requires_stable(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.1.0")

    with pytest.raises(RegistryConfigurationError, match="stable"):
        service.publish_version(
            "new_tool",
            "1.1.0",
            release_type="gray",
            gray_percentage=30,
            operator_id="admin",
        )

    assert _version_orm(db, "new_tool", "1.1.0").status == "draft"


def test_publish_stable_marks_published_stable(service: ToolRegistryService) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.0.0")

    published = service.publish_version("new_tool", "1.0.0", release_type="stable", operator_id="admin")

    assert published.status == "published"
    assert published.is_stable is True
    assert published.published_by == "admin"
    assert published.published_at is not None


def test_publish_second_stable_retires_previous(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.0.0")
    _create_version(service, "new_tool", "2.0.0")
    service.publish_version("new_tool", "1.0.0", release_type="stable", operator_id="admin")

    service.publish_version("new_tool", "2.0.0", release_type="stable", operator_id="admin")

    old = _version_orm(db, "new_tool", "1.0.0")
    new = _version_orm(db, "new_tool", "2.0.0")
    assert old.status == "retired"
    assert old.is_stable is False
    assert new.status == "published"
    assert new.is_stable is True


def test_publish_gray_stores_rollout_percentage_without_permission_policy(
    service: ToolRegistryService,
    db: Session,
) -> None:
    _create_query_tool(service, "new_tool")
    _create_version(service, "new_tool", "1.0.0")
    _create_version(service, "new_tool", "1.1.0")
    service.publish_version("new_tool", "1.0.0", release_type="stable", operator_id="admin")

    gray = service.publish_version(
        "new_tool",
        "1.1.0",
        release_type="gray",
        gray_percentage=30,
        operator_id="admin",
    )

    assert gray.status == "published"
    assert gray.is_stable is False
    assert gray.gray_percentage == 30
    policies = db.scalars(select(ToolPolicy).where(ToolPolicy.version_id == gray.id)).all()
    assert policies == []


@pytest.mark.parametrize("with_tool_deny", [False, True])
def test_publish_gray_never_synthesizes_permission_allow(
    service: ToolRegistryService,
    db: Session,
    with_tool_deny: bool,
) -> None:
    _create_query_tool(service, "governed_tool")
    _create_version(service, "governed_tool", "1.0.0")
    _create_version(service, "governed_tool", "1.1.0")
    service.publish_version(
        "governed_tool",
        "1.0.0",
        release_type="stable",
        operator_id="admin",
    )
    if with_tool_deny:
        service.replace_policies(
            "governed_tool",
            [PolicySpec(decision="deny")],
            operator_id="admin",
        )

    gray = service.publish_version(
        "governed_tool",
        "1.1.0",
        release_type="gray",
        gray_percentage=100,
        operator_id="admin",
    )

    version_policies = db.scalars(
        select(ToolPolicy).where(ToolPolicy.version_id == gray.id)
    ).all()
    assert version_policies == []
    registry = DatabaseToolRegistry(lambda: service.repository.load_snapshot())
    with pytest.raises(ToolForbiddenError):
        registry.resolve(
            "query.governed_tool",
            ToolContext(
                caller_type="external",
                tenant_id="tenant-a",
                role="operator",
            ),
        )


def test_commit_action_cannot_disable_confirmation(service: ToolRegistryService) -> None:
    service.create_tool(
        ToolCreateRequest(
            tool_key="commit_tool",
            capability="action.commit",
            name="commit tool",
            description="commit",
            tool_type="action",
            action_phase="commit",
        ),
        operator_id="admin",
    )

    with pytest.raises(RegistryConfigurationError, match="confirmation"):
        service.replace_policies(
            "commit_tool",
            [PolicySpec(decision="allow", requires_confirmation=False)],
            operator_id="admin",
        )


def test_replace_policies_replaces_all(service: ToolRegistryService, db: Session) -> None:
    _create_query_tool(service, "policy_tool")
    _create_version(service, "policy_tool", "1.0.0")
    service.publish_version("policy_tool", "1.0.0", release_type="stable", operator_id="admin")
    tool = _tool_orm(db, "policy_tool")
    db.add(
        ToolPolicy(
            tool_id=tool.id,
            version_id=None,
            tenant_id=None,
            role=None,
            decision="allow",
            rate_limit_per_minute=60,
            gray_percentage=0,
            requires_confirmation=False,
            enabled=True,
        )
    )
    db.commit()

    service.replace_policies(
        "policy_tool",
        [
            PolicySpec(
                version="1.0.0",
                tenant_id="tenant-a",
                role="operator",
                decision="deny",
                rate_limit_per_minute=10,
                gray_percentage=0,
                requires_confirmation=False,
            )
        ],
        operator_id="admin",
    )

    rows = db.scalars(select(ToolPolicy).where(ToolPolicy.tool_id == tool.id)).all()
    assert len(rows) == 2
    historical = next(row for row in rows if not row.enabled)
    active = next(row for row in rows if row.enabled)
    assert historical.decision == "allow"
    assert historical.active_scope_key is None
    assert active.tenant_id == "tenant-a"
    assert active.role == "operator"
    assert active.decision == "deny"
    assert active.rate_limit_per_minute == 10
    assert active.version_id is not None


def test_replace_policies_preserves_historical_audit_reference(
    service: ToolRegistryService,
    db: Session,
) -> None:
    _create_query_tool(service, "audit_policy_tool")
    tool = _tool_orm(db, "audit_policy_tool")
    old_policy = ToolPolicy(
        tool_id=tool.id,
        version_id=None,
        tenant_id=None,
        role=None,
        decision="allow",
        rate_limit_per_minute=60,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    )
    db.add(old_policy)
    db.flush()
    audit = ToolCallAudit(
        trace_id="trace-policy-history",
        tool_id=tool.id,
        version_id=None,
        implementation_ref=None,
        tenant_id="tenant-a",
        user_id="operator",
        role="operator",
        caller_type="internal",
        policy_id=old_policy.id,
        decision="allowed",
        status="success",
        argument_hash="hash-policy-history",
    )
    db.add(audit)
    db.commit()

    service.replace_policies(
        "audit_policy_tool",
        [PolicySpec(decision="deny")],
        operator_id="policy-admin",
    )
    db.refresh(audit)

    historical = db.get(ToolPolicy, old_policy.id)
    assert historical is not None
    assert historical.enabled is False
    assert audit.policy_id == old_policy.id
    active = db.scalars(
        select(ToolPolicy).where(
            ToolPolicy.tool_id == tool.id,
            ToolPolicy.enabled.is_(True),
        )
    ).all()
    assert len(active) == 1
    assert active[0].decision == "deny"


def test_retire_published_version(service: ToolRegistryService) -> None:
    _create_query_tool(service, "retire_tool")
    _create_version(service, "retire_tool", "1.0.0")
    service.publish_version("retire_tool", "1.0.0", release_type="stable", operator_id="admin")

    retired = service.retire_version("retire_tool", "1.0.0", operator_id="admin")

    assert retired.status == "retired"
    assert retired.is_stable is False


def test_management_mutations_persist_operator_ids(
    service: ToolRegistryService,
    db: Session,
) -> None:
    service.create_tool(
        ToolCreateRequest(
            tool_key="operator_tool",
            capability="query.operator",
            name="operator",
            description="operator",
            tool_type="query",
        ),
        operator_id="creator-1",
    )
    service.update_tool(
        "operator_tool",
        ToolUpdateRequest(description="updated"),
        operator_id="editor-1",
    )
    service.create_version(
        "operator_tool",
        VersionCreateRequest(
            version="1.0.0",
            implementation_ref="builtin.stub",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        ),
        operator_id="version-creator-1",
    )
    service.publish_version(
        "operator_tool",
        "1.0.0",
        release_type="stable",
        operator_id="publisher-1",
    )
    retired = service.retire_version(
        "operator_tool",
        "1.0.0",
        operator_id="retirer-1",
    )
    definition = _tool_orm(db, "operator_tool")

    assert definition.created_by == "creator-1"
    assert definition.updated_by == "editor-1"
    assert retired.created_by == "version-creator-1"
    assert retired.updated_by == "retirer-1"
    assert retired.published_by == "publisher-1"
    assert retired.retired_by == "retirer-1"
    assert retired.retired_at is not None


def test_publish_unknown_tool_raises_not_found(service: ToolRegistryService) -> None:
    with pytest.raises(ToolNotFoundError):
        service.publish_version("missing_tool", "1.0.0", release_type="stable", operator_id="admin")


def test_cache_invalidation_only_after_successful_commit(
    service: ToolRegistryService,
    invalidation_calls: list[str],
) -> None:
    _create_query_tool(service, "cache_tool")
    _create_version(service, "cache_tool", "1.0.0", implementation_ref="builtin.unbound")
    assert invalidation_calls == ["invalidated", "invalidated"]

    with pytest.raises(RegistryConfigurationError):
        service.publish_version("cache_tool", "1.0.0", release_type="stable", operator_id="admin")
    assert invalidation_calls == ["invalidated", "invalidated"]

    _create_version(service, "cache_tool", "2.0.0")
    service.publish_version("cache_tool", "2.0.0", release_type="stable", operator_id="admin")
    assert invalidation_calls == ["invalidated", "invalidated", "invalidated", "invalidated"]


def test_publish_locks_definition_row(service: ToolRegistryService, monkeypatch) -> None:
    _create_query_tool(service, "lock_tool")
    _create_version(service, "lock_tool", "1.0.0")

    calls: list[bool] = []
    original = service.repository.get_definition

    def spy(tool_key: str, *, for_update: bool = False):
        calls.append(for_update)
        return original(tool_key, for_update=for_update)

    monkeypatch.setattr(service.repository, "get_definition", spy)
    service.publish_version("lock_tool", "1.0.0", release_type="stable", operator_id="admin")

    assert calls == [True]


def test_replace_policies_locks_definition_row(
    service: ToolRegistryService,
    monkeypatch,
) -> None:
    _create_query_tool(service, "policy_lock_tool")
    calls: list[bool] = []
    original = service.repository.get_definition

    def spy(tool_key: str, *, for_update: bool = False):
        calls.append(for_update)
        return original(tool_key, for_update=for_update)

    monkeypatch.setattr(service.repository, "get_definition", spy)

    service.replace_policies(
        "policy_lock_tool",
        [PolicySpec(decision="allow")],
        operator_id="admin",
    )

    assert calls == [True]
