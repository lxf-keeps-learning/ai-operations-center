from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput
from app.tool_center.exceptions import RegistryConfigurationError, ToolNotFoundError
from app.tool_registry.executor_catalog import ExecutorCatalog
from app.tool_registry.models import ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.schemas import PolicySpec, ToolCreateRequest, VersionCreateRequest
from app.tool_registry.service import ToolRegistryService

from tests.tool_registry._helpers import make_sqlite_session_factory


class StubTool(BaseTool):
    name = "stub"
    description = "stub"

    def _execute(self, tool_input: BaseToolInput):
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


def test_publish_gray_updates_version_policy(service: ToolRegistryService, db: Session) -> None:
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
    policies = db.scalars(select(ToolPolicy).where(ToolPolicy.version_id == gray.id)).all()
    assert len(policies) == 1
    assert policies[0].gray_percentage == 30
    assert policies[0].tenant_id is None
    assert policies[0].role is None


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
    assert len(rows) == 1
    assert rows[0].tenant_id == "tenant-a"
    assert rows[0].role == "operator"
    assert rows[0].decision == "deny"
    assert rows[0].rate_limit_per_minute == 10
    assert rows[0].version_id is not None


def test_retire_published_version(service: ToolRegistryService) -> None:
    _create_query_tool(service, "retire_tool")
    _create_version(service, "retire_tool", "1.0.0")
    service.publish_version("retire_tool", "1.0.0", release_type="stable", operator_id="admin")

    retired = service.retire_version("retire_tool", "1.0.0", operator_id="admin")

    assert retired.status == "retired"
    assert retired.is_stable is False


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
