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


def test_seed_marks_draft_tool_as_action_prepare(session: Session) -> None:
    seed_builtin_tools(session)
    session.commit()

    tool = session.scalar(
        select(ToolDefinition).where(ToolDefinition.tool_key == "work_order_draft")
    )

    assert tool is not None
    assert tool.tool_type == "action"
    assert tool.action_phase == "prepare"
