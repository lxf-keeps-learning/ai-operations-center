from __future__ import annotations

import logging

import pytest

from app.core.trace.trace_context import clear_trace_id, set_trace_id
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_center.exceptions import RegistryUnavailableError, ToolForbiddenError
from app.tool_registry.contracts import ActionPhase, GovernanceDecision, ToolType
from app.tool_registry.registry import DatabaseToolRegistry

from tests.tool_registry._helpers import (
    FakeClock,
    SnapshotLoader,
    build_gateway,
    make_definition,
    make_policy,
    make_version,
)

INTERNAL = ToolContext(caller_type="internal", tenant_id="tenant-a", role="operator", user_id="u1")
INTERNAL_NO_TENANT = ToolContext(caller_type="internal")

KPI = make_definition(1, "kpi_query", "query.kpi", "KPI Query", "Returns KPI data")
KPI_STABLE = make_version(11, 1, implementation_ref="builtin.kpi_query")
KPI_GRAY = make_version(
    12,
    1,
    version="1.1.0",
    implementation_ref="builtin.kpi_query.v110",
    is_stable=False,
    gray_percentage=100,
)
KPI_POLICY = make_policy(1, 1)
GRAY_POLICY = make_policy(2, 1, version_id=12, gray_percentage=100)

DRAFT_TOOL = make_definition(
    4,
    "work_order_draft",
    "action.work_order.draft",
    tool_type=ToolType.ACTION,
    action_phase=ActionPhase.PREPARE,
)
DRAFT_VERSION = make_version(41, 4, implementation_ref="builtin.work_order_draft")
DRAFT_POLICY = make_policy(4, 4)

COMMIT_TOOL = make_definition(
    5,
    "work_order_commit",
    "action.work_order.commit",
    tool_type=ToolType.ACTION,
    action_phase=ActionPhase.COMMIT,
)
COMMIT_VERSION = make_version(51, 5, implementation_ref="builtin.work_order_commit")
COMMIT_POLICY = make_policy(5, 5)


class StubQueryTool(BaseTool):
    name = "kpi_query"
    description = "stub"

    async def _execute(self, tool_input: BaseToolInput):
        return {"total": 3}, [], {}


class StubPrepareTool(BaseTool):
    name = "work_order_draft"
    description = "stub"

    async def _execute(self, tool_input: BaseToolInput):
        return {"draft_id": "d1", "requires_human_confirmation": True}, [], {}


class StubCommitTool(BaseTool):
    name = "work_order_commit"
    description = "stub"

    def __init__(self) -> None:
        self.calls = 0

    async def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        return {"committed": True}, [], {}


def _gateway(clock: FakeClock, *, repository_factory=None, stale_query_ttl_seconds: int = 86400):
    return build_gateway(
        (KPI, DRAFT_TOOL, COMMIT_TOOL),
        (KPI_STABLE, KPI_GRAY, DRAFT_VERSION, COMMIT_VERSION),
        (KPI_POLICY, GRAY_POLICY, DRAFT_POLICY, COMMIT_POLICY),
        executors={
            "builtin.kpi_query": StubQueryTool(),
            "builtin.kpi_query.v110": StubQueryTool(),
            "builtin.work_order_draft": StubPrepareTool(),
            "builtin.work_order_commit": StubCommitTool(),
        },
        clock=clock,
        repository_factory=repository_factory,
        stale_query_ttl_seconds=stale_query_ttl_seconds,
    )


def test_database_failure_with_fresh_cache_serves_everything() -> None:
    clock = FakeClock()
    gateway, loader, _sf = _gateway(clock)
    gateway.execute("query.kpi", {}, INTERNAL)
    gateway.execute("action.work_order.draft", {}, INTERNAL)
    clock.advance(seconds=10)
    loader.failing = True

    query = gateway.execute("query.kpi", {}, INTERNAL)
    draft = gateway.execute("action.work_order.draft", {}, INTERNAL)

    assert query.success is True
    assert draft.success is True


def test_stale_snapshot_serves_query_but_rejects_actions() -> None:
    clock = FakeClock()
    gateway, loader, _sf = _gateway(clock)
    gateway.execute("query.kpi", {}, INTERNAL)
    clock.advance(seconds=31)
    loader.failing = True

    query = gateway.execute("query.kpi", {}, INTERNAL)
    draft = gateway.execute("action.work_order.draft", {}, INTERNAL)

    assert query.success is True
    assert query.metadata["selected_stable"] is True
    assert draft.success is False
    assert draft.error is not None
    assert draft.error.code == "TOOL_REGISTRY_UNAVAILABLE"


def test_stale_snapshot_never_selects_gray() -> None:
    clock = FakeClock()
    gateway, loader, _sf = _gateway(clock)
    gateway.execute("query.kpi", {}, INTERNAL)
    clock.advance(seconds=31)
    loader.failing = True

    query = gateway.execute("query.kpi", {}, INTERNAL)

    assert query.metadata["tool_version"] == "1.0.0"
    assert query.metadata["selected_stable"] is True


def test_expired_snapshot_returns_unavailable() -> None:
    clock = FakeClock()
    gateway, loader, _sf = _gateway(clock, stale_query_ttl_seconds=60)
    gateway.execute("query.kpi", {}, INTERNAL)
    clock.advance(seconds=61)
    loader.failing = True

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_REGISTRY_UNAVAILABLE"


def test_audit_write_failure_preserves_result_and_logs_trace(caplog) -> None:
    def failing_factory():
        raise OSError("audit database down")

    clock = FakeClock()
    gateway, _loader, _sf = _gateway(clock, repository_factory=failing_factory)
    set_trace_id("trace-failure-mode-1")
    try:
        with caplog.at_level(logging.ERROR, logger="ioc.tool_registry"):
            result = gateway.execute("query.kpi", {}, INTERNAL)
    finally:
        clear_trace_id()

    assert result.success is True
    assert "TOOL_AUDIT_WRITE_FAILED" in caplog.text
    assert "trace-failure-mode-1" in caplog.text


def test_cross_tenant_policy_isolation() -> None:
    deny_tenant_a = make_policy(
        9,
        1,
        tenant_id="tenant-a",
        role="operator",
        decision=GovernanceDecision.DENY,
    )
    loader = SnapshotLoader((KPI,), (KPI_STABLE,), (KPI_POLICY, deny_tenant_a))
    registry = DatabaseToolRegistry(loader, cache_ttl_seconds=30, clock=FakeClock())

    tenant_b = ToolContext(
        caller_type="internal",
        tenant_id="tenant-b",
        role="operator",
        user_id="u2",
    )
    resolved_b = registry.resolve("query.kpi", tenant_b)
    assert resolved_b.policy_id == KPI_POLICY.id

    with pytest.raises(ToolForbiddenError):
        registry.resolve("query.kpi", INTERNAL)


def test_confirmation_expiry_rejects_commit() -> None:
    clock = FakeClock()
    gateway, _loader, _sf, commit_tool = _gateway_with_commit_tool(clock)
    set_trace_id("trace-expiry-1")
    try:
        first = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL)
        token = first.metadata["confirmation_token"]

        clock.advance(seconds=301)
        retry = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert retry.success is False
    assert retry.error is not None
    assert retry.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert commit_tool.calls == 0


def _gateway_with_commit_tool(clock: FakeClock):
    commit_tool = StubCommitTool()
    gateway, loader, session_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": commit_tool},
        clock=clock,
    )
    return gateway, loader, session_factory, commit_tool
