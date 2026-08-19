from __future__ import annotations

from collections.abc import Iterator
import sqlite3

import pytest
from jsonschema.validators import validator_for
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.tool_registry.contracts import GovernanceDecision, ToolType, VersionStatus
from app.tool_registry.models import ToolCallAudit, ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.repository import AuditFilters, ToolRegistryRepository


def _enable_foreign_keys(dbapi_connection: sqlite3.Connection, _record: object) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def _tool_definition(
    *,
    tool_key: str,
    capability: str,
    tool_type: str = "query",
    action_phase: str | None = None,
    enabled: bool = True,
) -> ToolDefinition:
    return ToolDefinition(
        tool_key=tool_key,
        capability=capability,
        name=tool_key,
        description=f"description for {tool_key}",
        tool_type=tool_type,
        action_phase=action_phase,
        enabled=enabled,
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        yield db

    Base.metadata.drop_all(engine)


def test_load_snapshot_filters_runtime_rows_and_returns_immutable_records(session: Session) -> None:
    enabled_tool = _tool_definition(tool_key="kpi_query", capability="query.kpi")
    disabled_tool = _tool_definition(tool_key="alarm_query", capability="query.alarm", enabled=False)
    session.add_all([enabled_tool, disabled_tool])
    session.flush()

    published_version = ToolVersion(
        tool_id=enabled_tool.id,
        version="1.0.0",
        implementation_ref="builtin.kpi_query",
        input_schema={"type": "object", "title": "KPI input"},
        output_schema={"type": "object", "title": "KPI output"},
        status="published",
        is_stable=True,
    )
    draft_version = ToolVersion(
        tool_id=enabled_tool.id,
        version="2.0.0",
        implementation_ref="builtin.kpi_query.next",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="draft",
        is_stable=False,
    )
    disabled_tool_version = ToolVersion(
        tool_id=disabled_tool.id,
        version="1.0.0",
        implementation_ref="builtin.alarm_query",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="published",
        is_stable=True,
    )
    session.add_all([published_version, draft_version, disabled_tool_version])
    session.flush()

    enabled_policy = ToolPolicy(
        tool_id=enabled_tool.id,
        version_id=None,
        tenant_id=None,
        role=None,
        decision="allow",
        rate_limit_per_minute=60,
        gray_percentage=25,
        requires_confirmation=False,
        enabled=True,
        updated_by="seed",
    )
    disabled_policy = ToolPolicy(
        tool_id=enabled_tool.id,
        version_id=published_version.id,
        tenant_id="tenant-a",
        role="operator",
        decision="deny",
        rate_limit_per_minute=1,
        gray_percentage=0,
        requires_confirmation=True,
        enabled=False,
        updated_by="seed",
    )
    session.add_all([enabled_policy, disabled_policy])
    session.commit()

    statements: list[str] = []

    def _collect_sql(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = session.get_bind()
    assert engine is not None
    event.listen(engine, "before_cursor_execute", _collect_sql)
    try:
        snapshot = ToolRegistryRepository(session).load_snapshot()
    finally:
        event.remove(engine, "before_cursor_execute", _collect_sql)

    session.close()

    assert len(statements) == 3
    assert len(snapshot.definitions) == 1
    assert len(snapshot.versions) == 1
    assert len(snapshot.policies) == 1
    assert snapshot.definitions[0].tool_key == "kpi_query"
    assert snapshot.definitions[0].tool_type is ToolType.QUERY
    assert snapshot.versions[0].status is VersionStatus.PUBLISHED
    assert snapshot.versions[0].implementation_ref == "builtin.kpi_query"
    assert snapshot.policies[0].decision is GovernanceDecision.ALLOW
    assert snapshot.policies[0].gray_percentage == 25


def test_load_snapshot_freezes_schema_values_without_mutating_orm_json(session: Session) -> None:
    tool = _tool_definition(tool_key="schema_query", capability="query.schema")
    session.add(tool)
    session.flush()
    original_input_schema = {
        "type": "object",
        "required": ["filters"],
        "properties": {
            "filters": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
    }
    original_output_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "object"},
            }
        },
    }
    version = ToolVersion(
        tool_id=tool.id,
        version="1.0.0",
        implementation_ref="builtin.schema_query",
        input_schema=original_input_schema,
        output_schema=original_output_schema,
        status="published",
        is_stable=True,
    )
    session.add(version)
    session.commit()

    snapshot = ToolRegistryRepository(session).load_snapshot()
    frozen_input_schema = snapshot.versions[0].input_schema
    frozen_output_schema = snapshot.versions[0].output_schema

    assert frozen_input_schema is not version.input_schema
    assert frozen_output_schema is not version.output_schema
    assert frozen_input_schema["required"] is not version.input_schema["required"]
    assert frozen_input_schema["properties"] is not version.input_schema["properties"]

    validator_for(frozen_input_schema).check_schema(frozen_input_schema)

    with pytest.raises(TypeError):
        frozen_input_schema["title"] = "mutated"

    with pytest.raises(TypeError):
        frozen_input_schema["properties"]["filters"]["type"] = "object"

    with pytest.raises(TypeError):
        frozen_input_schema["required"].append("tenant_id")

    assert version.input_schema == original_input_schema
    assert version.output_schema == original_output_schema
    assert isinstance(version.input_schema["required"], list)
    assert version.input_schema["properties"]["filters"]["type"] == "array"


def test_append_list_and_update_audit_preserves_history(session: Session) -> None:
    tool = _tool_definition(tool_key="risk_query", capability="query.risk")
    session.add(tool)
    session.flush()
    version = ToolVersion(
        tool_id=tool.id,
        version="1.0.0",
        implementation_ref="builtin.risk_query",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="published",
        is_stable=True,
    )
    session.add(version)
    session.flush()
    policy = ToolPolicy(
        tool_id=tool.id,
        version_id=None,
        tenant_id=None,
        role=None,
        decision="allow",
        rate_limit_per_minute=60,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
        updated_by="seed",
    )
    session.add(policy)
    session.commit()

    repository = ToolRegistryRepository(session)
    created = repository.append_audit(
        ToolCallAudit(
            trace_id="trace-risk-query",
            tool_id=tool.id,
            version_id=version.id,
            implementation_ref=version.implementation_ref,
            tenant_id="tenant-a",
            user_id="operator-1",
            role="analyst",
            caller_type="internal",
            policy_id=policy.id,
            decision="allowed",
            gray_bucket=0,
            selected_stable=True,
            status="pending",
            duration_ms=None,
            error_code=None,
            argument_hash="hash-risk-query",
            argument_summary={"site": "plant-a"},
        )
    )
    session.commit()

    audits, total = repository.list_audits(
        AuditFilters(trace_id="trace-risk-query", tool_id=tool.id, status="pending"),
        offset=0,
        limit=10,
    )

    assert total == 1
    assert audits[0].id == created.id
    assert audits[0].trace_id == "trace-risk-query"

    repository.update_audit(created.id, status="success", duration_ms=14, error_code=None)
    session.commit()

    stored = session.scalar(select(ToolCallAudit).where(ToolCallAudit.id == created.id))
    assert stored is not None
    assert stored.status == "success"
    assert stored.duration_ms == 14
    assert stored.error_code is None
