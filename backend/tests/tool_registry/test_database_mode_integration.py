from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings
from app.tool_center.contracts import ToolContext
from app.tool_registry import compat
from app.tool_registry.compat import execute_tool, reset_runtime_for_tests
from app.tool_registry.models import ToolCallAudit
from app.tool_registry.schemas import PolicySpec, VersionCreateRequest
from app.tool_registry.seed import seed_builtin_tools
from app.tool_registry.service import ToolRegistryService
from app.tools.register import register_all_tools

from tests.tool_registry._helpers import make_sqlite_session_factory

INTERNAL = ToolContext(caller_type="internal", tenant_id="tenant-a", role="operator", user_id="u1")
NO_TENANT_INTERNAL = ToolContext(caller_type="internal")

DRAFT_ARGS = {
    "source_type": "alarm",
    "source_id": "alarm_001",
    "title": "处理冷站出水温度异常",
    "description": "基于告警 alarm_001 生成工单草稿",
    "priority": "high",
}


@pytest.fixture
def database_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    session_factory = make_sqlite_session_factory()
    with session_factory() as session:
        seed_builtin_tools(session)
        session.commit()
    register_all_tools()
    monkeypatch.setattr(compat, "get_session_local", lambda: session_factory)
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    reset_runtime_for_tests()
    yield session_factory
    reset_runtime_for_tests()
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")


def _audit_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(ToolCallAudit)) or 0


def test_legacy_name_and_capability_execute_with_governance(database_runtime) -> None:
    by_name = execute_tool("kpi_query", {"department": "安全环保部"}, INTERNAL)
    by_capability = execute_tool("query.kpi", {"department": "安全环保部"}, INTERNAL)

    assert by_name.success is True
    assert by_name.metadata["tool_key"] == "kpi_query"
    assert by_name.metadata["tool_version"] == "1.0.0"
    assert by_name.metadata["implementation_ref"] == "builtin.kpi_query"
    assert by_name.metadata["selected_stable"] is True
    assert by_capability.success is True
    assert _audit_count(database_runtime) == 2


def test_draft_action_executes_through_gateway(database_runtime) -> None:
    result = execute_tool("action.work_order.draft", DRAFT_ARGS, INTERNAL)

    assert result.success is True
    assert result.data["requires_human_confirmation"] is True
    assert result.metadata["tool_key"] == "work_order_draft"
    assert result.metadata["tool_version"] == "1.0.0"


def test_publish_gray_selects_stable_by_tenant_hash(database_runtime) -> None:
    with database_runtime() as session:
        service = ToolRegistryService(session)
        service.create_version(
            "kpi_query",
            VersionCreateRequest(
                version="1.1.0",
                implementation_ref="builtin.kpi_query",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
            operator_id="admin",
        )
        service.publish_version(
            "kpi_query",
            "1.1.0",
            release_type="gray",
            gray_percentage=100,
            operator_id="admin",
        )

    gray_hit = execute_tool("query.kpi", {}, INTERNAL)
    stable_only = execute_tool("query.kpi", {}, NO_TENANT_INTERNAL)

    assert gray_hit.metadata["tool_version"] == "1.1.0"
    assert gray_hit.metadata["selected_stable"] is False
    assert gray_hit.metadata["gray_bucket"] is not None
    assert stable_only.metadata["tool_version"] == "1.0.0"
    assert stable_only.metadata["selected_stable"] is True


def test_retire_gray_falls_back_to_stable(database_runtime) -> None:
    with database_runtime() as session:
        service = ToolRegistryService(session)
        service.create_version(
            "kpi_query",
            VersionCreateRequest(
                version="1.1.0",
                implementation_ref="builtin.kpi_query",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
            operator_id="admin",
        )
        service.publish_version(
            "kpi_query",
            "1.1.0",
            release_type="gray",
            gray_percentage=100,
            operator_id="admin",
        )

    before = execute_tool("query.kpi", {}, INTERNAL)
    assert before.metadata["tool_version"] == "1.1.0"

    with database_runtime() as session:
        ToolRegistryService(session).retire_version("kpi_query", "1.1.0", operator_id="admin")

    after = execute_tool("query.kpi", {}, INTERNAL)

    assert after.metadata["tool_version"] == "1.0.0"
    assert after.metadata["selected_stable"] is True


def test_permission_denial_blocks_calls(database_runtime) -> None:
    with database_runtime() as session:
        ToolRegistryService(session).replace_policies(
            "kpi_query",
            [PolicySpec(decision="deny")],
            operator_id="admin",
        )

    result = execute_tool("query.kpi", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_FORBIDDEN"


def test_rate_limit_blocks_beyond_policy_limit(database_runtime) -> None:
    with database_runtime() as session:
        ToolRegistryService(session).replace_policies(
            "kpi_query",
            [PolicySpec(decision="allow", rate_limit_per_minute=3)],
            operator_id="admin",
        )

    results = [execute_tool("query.kpi", {}, INTERNAL) for _ in range(4)]

    assert [result.success for result in results] == [True, True, True, False]
    assert results[3].error is not None
    assert results[3].error.code == "TOOL_RATE_LIMITED"


def test_legacy_rollback_restores_direct_registry_path(
    database_runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")

    result = execute_tool("kpi_query", {"department": "安全环保部"}, INTERNAL)

    assert result.success is True
    assert result.metadata["source"] == "mock_ioc_api"
    assert "tool_version" not in result.metadata
    assert _audit_count(database_runtime) == 0
