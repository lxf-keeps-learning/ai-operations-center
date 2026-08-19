from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sqlite3
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import Base
from app.tool_registry.models import ToolCallAudit, ToolDefinition, ToolPolicy, ToolVersion


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def _enable_foreign_keys(dbapi_connection: sqlite3.Connection, _record: object) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    from sqlalchemy import event

    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as db:
        yield db

    Base.metadata.drop_all(engine)


def test_tool_definition_and_version_constraints(session: Session) -> None:
    """Dropping the unique version guard would allow duplicate semantic releases."""
    tool = ToolDefinition(
        tool_key="kpi_query",
        capability="query.kpi",
        name="KPI",
        description="desc",
        tool_type="query",
        action_phase=None,
        enabled=True,
    )
    session.add(tool)
    session.flush()
    session.add(
        ToolVersion(
            tool_id=tool.id,
            version="1.0.0",
            implementation_ref="builtin.kpi_query",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            status="published",
            is_stable=True,
        )
    )
    session.commit()

    assert session.scalar(
        select(ToolDefinition).where(ToolDefinition.capability == "query.kpi")
    ) is tool

    session.add(
        ToolVersion(
            tool_id=tool.id,
            version="1.0.0",
            implementation_ref="builtin.kpi_query_duplicate",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            status="draft",
            is_stable=False,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_tool_call_audit_allows_unresolved_tool_reference(session: Session) -> None:
    """Removing nullable audit references would break resolution-failure traces."""
    session.add(
        ToolCallAudit(
            trace_id="trace-unresolved",
            tool_id=None,
            version_id=None,
            implementation_ref=None,
            tenant_id="tenant-a",
            user_id="operator",
            role="analyst",
            caller_type="internal",
            policy_id=None,
            decision="denied",
            gray_bucket=None,
            selected_stable=None,
            status="skipped",
            duration_ms=None,
            error_code="capability_not_found",
            argument_hash="hash-1",
            argument_summary={"query": "***"},
        )
    )
    session.commit()

    stored = session.scalar(
        select(ToolCallAudit).where(ToolCallAudit.trace_id == "trace-unresolved")
    )

    assert stored is not None
    assert stored.tool_id is None
    assert stored.version_id is None


def test_tool_policy_indexes_cover_specificity_lookup() -> None:
    indexes = {
        index.name: tuple(index.columns.keys())
        for index in ToolPolicy.__table__.indexes
    }

    assert indexes["ix_tool_policies_scope"] == (
        "tool_id",
        "version_id",
        "tenant_id",
        "role",
        "enabled",
    )
    assert indexes["ix_tool_policies_enabled"] == ("enabled",)


def test_rollout_percentage_is_stored_only_on_policies() -> None:
    assert "gray_percentage" not in ToolVersion.__table__.c.keys()
    assert "gray_percentage" in ToolPolicy.__table__.c.keys()


def test_deleting_a_definition_cascades_versions_and_policies_but_keeps_audits(
    session: Session,
) -> None:
    """Replacing audit retention with delete cascade would erase governance history."""
    tool = ToolDefinition(
        tool_key="draft_work_order",
        capability="action.work_order.prepare",
        name="Draft work order",
        description="Prepare work order payload",
        tool_type="action",
        action_phase="prepare",
        enabled=True,
    )
    session.add(tool)
    session.flush()

    version = ToolVersion(
        tool_id=tool.id,
        version="1.0.0",
        implementation_ref="builtin.work_order.prepare",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="published",
        is_stable=True,
    )
    session.add(version)
    session.flush()

    policy = ToolPolicy(
        tool_id=tool.id,
        version_id=version.id,
        tenant_id="tenant-a",
        role="operator",
        decision="allow",
        rate_limit_per_minute=60,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    )
    session.add(policy)
    session.flush()

    audit = ToolCallAudit(
        trace_id="trace-keep-audit",
        tool_id=tool.id,
        version_id=version.id,
        implementation_ref=version.implementation_ref,
        tenant_id="tenant-a",
        user_id="operator",
        role="operator",
        caller_type="internal",
        policy_id=policy.id,
        decision="allowed",
        gray_bucket=42,
        selected_stable=True,
        status="success",
        duration_ms=17,
        error_code=None,
        argument_hash="hash-2",
        argument_summary={"title": "replace filter"},
    )
    session.add(audit)
    session.commit()

    version_id = version.id
    policy_id = policy.id
    session.delete(tool)
    session.commit()
    session.expire_all()

    assert session.scalar(select(ToolVersion).where(ToolVersion.id == version_id)) is None
    assert session.scalar(select(ToolPolicy).where(ToolPolicy.id == policy_id)) is None

    stored_audit = session.scalar(
        select(ToolCallAudit).where(ToolCallAudit.trace_id == "trace-keep-audit")
    )
    assert stored_audit is not None
    assert stored_audit.tool_id is None
    assert stored_audit.version_id is None
    assert stored_audit.policy_id is None
