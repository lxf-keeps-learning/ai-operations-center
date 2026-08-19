from __future__ import annotations

from collections.abc import Iterator
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.tool_registry.models import ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.seed import BUILTIN_TOOLS, seed_builtin_tools


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


def test_seed_builtin_tools_is_idempotent(session: Session) -> None:
    seed_builtin_tools(session)
    seed_builtin_tools(session)
    session.commit()

    assert session.scalar(select(func.count()).select_from(ToolDefinition)) == 6
    assert session.scalar(select(func.count()).select_from(ToolVersion)) == 6
    assert session.scalar(select(func.count()).select_from(ToolPolicy)) == 6

    tools = session.scalars(select(ToolDefinition).order_by(ToolDefinition.tool_key)).all()
    versions = session.scalars(select(ToolVersion).order_by(ToolVersion.implementation_ref)).all()
    policies = session.scalars(select(ToolPolicy).order_by(ToolPolicy.tool_id)).all()

    expected_refs = sorted(spec.implementation_ref for spec in BUILTIN_TOOLS)

    assert sorted(tool.capability for tool in tools) == sorted(spec.capability for spec in BUILTIN_TOOLS)
    assert [version.version for version in versions] == ["1.0.0"] * 6
    assert [version.status for version in versions] == ["published"] * 6
    assert [version.is_stable for version in versions] == [True] * 6
    assert [version.implementation_ref for version in versions] == expected_refs
    assert all(policy.decision == "allow" for policy in policies)
    assert all(policy.rate_limit_per_minute == 60 for policy in policies)
    assert all(policy.enabled for policy in policies)
    assert all(policy.version_id is None for policy in policies)
    assert all(tool.created_by == "system" and tool.updated_by == "system" for tool in tools)
    assert all(
        version.created_by == "system" and version.updated_by == "system"
        for version in versions
    )


def test_seed_marks_draft_tool_as_action_prepare(session: Session) -> None:
    seed_builtin_tools(session)
    session.commit()

    tool = session.scalar(
        select(ToolDefinition).where(ToolDefinition.tool_key == "work_order_draft")
    )

    assert tool is not None
    assert tool.tool_type == "action"
    assert tool.action_phase == "prepare"


def test_seed_rerun_preserves_disabled_retired_and_deny_governance(
    session: Session,
) -> None:
    seed_builtin_tools(session)
    definition = session.scalar(
        select(ToolDefinition).where(ToolDefinition.tool_key == "kpi_query")
    )
    version = session.scalar(
        select(ToolVersion).where(
            ToolVersion.tool_id == definition.id,
            ToolVersion.version == "1.0.0",
        )
    )
    policy = session.scalar(
        select(ToolPolicy).where(
            ToolPolicy.tool_id == definition.id,
            ToolPolicy.version_id.is_(None),
            ToolPolicy.tenant_id.is_(None),
            ToolPolicy.role.is_(None),
        )
    )
    definition.enabled = False
    version.status = "retired"
    version.is_stable = False
    policy.decision = "deny"
    session.flush()

    seed_builtin_tools(session)

    assert definition.enabled is False
    assert version.status == "retired"
    assert version.is_stable is False
    assert policy.decision == "deny"


def test_seed_rerun_preserves_newer_stable_version(session: Session) -> None:
    seed_builtin_tools(session)
    definition = session.scalar(
        select(ToolDefinition).where(ToolDefinition.tool_key == "alarm_query")
    )
    baseline = session.scalar(
        select(ToolVersion).where(
            ToolVersion.tool_id == definition.id,
            ToolVersion.version == "1.0.0",
        )
    )
    baseline.status = "retired"
    baseline.is_stable = False
    newer = ToolVersion(
        tool_id=definition.id,
        version="2.0.0",
        implementation_ref="builtin.alarm_query.v2",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="published",
        is_stable=True,
    )
    session.add(newer)
    session.flush()

    seed_builtin_tools(session)

    assert newer.status == "published"
    assert newer.is_stable is True
    assert baseline.status == "retired"
    assert baseline.is_stable is False
