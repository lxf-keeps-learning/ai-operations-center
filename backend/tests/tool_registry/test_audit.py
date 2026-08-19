from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.trace.trace_context import clear_trace_id, set_trace_id
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_center.exceptions import ToolException
from app.tool_center.telemetry import hash_arguments
from app.tool_registry.contracts import ActionPhase, ToolType
from app.tool_registry.models import ToolCallAudit

from tests.tool_registry._helpers import (
    build_gateway,
    make_definition,
    make_policy,
    make_version,
)

KPI = make_definition(1, "kpi_query", "query.kpi", "KPI Query", "Returns KPI data")
KPI_VERSION = make_version(11, 1, implementation_ref="builtin.kpi_query")
KPI_POLICY = make_policy(1, 1)

COMMIT_TOOL = make_definition(
    5,
    "work_order_commit",
    "action.work_order.commit",
    tool_type=ToolType.ACTION,
    action_phase=ActionPhase.COMMIT,
)
COMMIT_VERSION = make_version(51, 5, implementation_ref="builtin.work_order_commit")
COMMIT_POLICY = make_policy(5, 5)

INTERNAL = ToolContext(
    caller_type="internal",
    tenant_id="tenant-a",
    role="operator",
    user_id="operator-1",
)


class StubQueryTool(BaseTool):
    name = "kpi_query"
    description = "Stub KPI query"

    def __init__(self) -> None:
        self.calls = 0

    async def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        return {"total": 3}, [], {}


class StubFailingTool(BaseTool):
    name = "kpi_query"
    description = "Stub failing tool"

    async def _execute(self, tool_input: BaseToolInput):
        raise ToolException(
            code="TOOL_UPSTREAM_ERROR",
            message="upstream down",
            retryable=False,
        )


class StubCommitTool(BaseTool):
    name = "work_order_commit"
    description = "Stub commit tool"

    def __init__(self) -> None:
        self.calls = 0

    async def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        return {"committed": True}, [], {}


def _gateway(executor=None, *, repository_factory=None):
    return build_gateway(
        (KPI,),
        (KPI_VERSION,),
        (KPI_POLICY,),
        executors={"builtin.kpi_query": executor or StubQueryTool()},
        repository_factory=repository_factory,
    )


def _audits(session: Session) -> list[ToolCallAudit]:
    return list(session.scalars(select(ToolCallAudit).order_by(ToolCallAudit.id)))


def test_allowed_success_is_audited_with_hash_and_summary() -> None:
    gateway, _loader, session_factory = _gateway()

    set_trace_id("trace-audit-1")
    try:
        result = gateway.execute("query.kpi", {"department": "安全环保部"}, INTERNAL)
    finally:
        clear_trace_id()

    assert result.success is True
    with session_factory() as session:
        rows = _audits(session)
        assert len(rows) == 1
        row = rows[0]
        assert row.trace_id == result.trace_id
        assert row.decision == "allowed"
        assert row.status == "success"
        assert row.duration_ms is not None and row.duration_ms >= 1
        assert row.error_code is None
        assert row.tool_id == 1
        assert row.version_id == 11
        assert row.policy_id == 1
        assert row.implementation_ref == "builtin.kpi_query"
        assert row.tenant_id == "tenant-a"
        assert row.user_id == "operator-1"
        assert row.role == "operator"
        assert row.caller_type == "internal"
        assert row.argument_hash == hash_arguments({"department": "安全环保部"})
        assert row.argument_summary == {"department": "安全环保部"}


def test_denied_decision_is_audited() -> None:
    from app.tool_registry.contracts import GovernanceDecision

    deny = make_policy(2, 1, decision=GovernanceDecision.DENY)
    gateway, _loader, session_factory = build_gateway(
        (KPI,),
        (KPI_VERSION,),
        (deny,),
        executors={"builtin.kpi_query": StubQueryTool()},
    )

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.success is False
    with session_factory() as session:
        row = _audits(session)[0]
        assert row.decision == "denied"
        assert row.status == "failed"
        assert row.error_code == "TOOL_FORBIDDEN"
        assert row.policy_id == 2
        assert row.tool_id == KPI.id
        assert row.version_id == KPI_VERSION.id
        assert row.implementation_ref == KPI_VERSION.implementation_ref
        assert row.gray_bucket is None
        assert row.selected_stable is True
        assert row.tool_key_snapshot == KPI.tool_key
        assert row.capability_snapshot == KPI.capability
        assert row.version_snapshot == KPI_VERSION.version
        assert row.policy_snapshot["decision"] == "deny"


def test_no_policy_external_denial_keeps_immutable_resolution_snapshot() -> None:
    external = INTERNAL.model_copy(update={"caller_type": "external"})
    gateway, _loader, session_factory = build_gateway(
        (KPI,),
        (KPI_VERSION,),
        (),
        executors={"builtin.kpi_query": StubQueryTool()},
    )

    result = gateway.execute("query.kpi", {}, external)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_FORBIDDEN"
    with session_factory() as session:
        row = _audits(session)[0]
        assert row.policy_id is None
        assert row.tool_key_snapshot == KPI.tool_key
        assert row.capability_snapshot == KPI.capability
        assert row.version_snapshot == KPI_VERSION.version
        assert row.implementation_ref == KPI_VERSION.implementation_ref
        assert row.selected_stable is True
        assert row.policy_snapshot == {
            "policy_id": None,
            "decision": "deny",
            "rate_limit_per_minute": None,
            "requires_confirmation": None,
            "reason": "no_matching_policy",
        }


def test_rate_limited_decision_is_audited() -> None:
    limited = make_policy(9, 1, rate_limit_per_minute=1)
    gateway, _loader, session_factory = build_gateway(
        (KPI,),
        (KPI_VERSION,),
        (limited,),
        executors={"builtin.kpi_query": StubQueryTool()},
    )

    gateway.execute("query.kpi", {}, INTERNAL)
    blocked = gateway.execute("query.kpi", {}, INTERNAL)

    assert blocked.success is False
    with session_factory() as session:
        rows = _audits(session)
        assert [row.decision for row in rows] == ["allowed", "rate_limited"]
        assert rows[1].status == "failed"
        assert rows[1].error_code == "TOOL_RATE_LIMITED"
        assert rows[1].policy_id == 9


def test_confirmation_required_decision_is_audited() -> None:
    gateway, _loader, session_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": StubCommitTool()},
    )

    result = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL)

    assert result.success is False
    with session_factory() as session:
        row = _audits(session)[0]
        assert row.decision == "confirmation_required"
        assert row.error_code == "TOOL_CONFIRMATION_REQUIRED"
        assert row.argument_hash == hash_arguments({"draft_id": "d1"})


def test_tool_failure_is_audited() -> None:
    gateway, _loader, session_factory = _gateway(executor=StubFailingTool())

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    with session_factory() as session:
        row = _audits(session)[0]
        assert row.decision == "allowed"
        assert row.status == "failed"
        assert row.error_code == "TOOL_UPSTREAM_ERROR"
        assert row.duration_ms is not None


def test_argument_hash_changes_with_arguments() -> None:
    gateway, _loader, _sf = _gateway()

    gateway.execute("query.kpi", {"a": 1}, INTERNAL)
    gateway.execute("query.kpi", {"a": 2}, INTERNAL)
    gateway.execute("query.kpi", {"a": 1}, INTERNAL)

    first_hash = hash_arguments({"a": 1})
    second_hash = hash_arguments({"a": 2})
    assert first_hash != second_hash
    with _sf() as session:
        hashes = [row.argument_hash for row in _audits(session)]
        assert hashes == [first_hash, second_hash, first_hash]


def test_argument_summary_sanitizes_sensitive_keys() -> None:
    gateway, _loader, session_factory = _gateway()

    result = gateway.execute(
        "query.kpi",
        {"password": "hunter2", "nested": {"token": "secret-token"}},
        INTERNAL,
    )

    assert result.success is True
    with session_factory() as session:
        row = _audits(session)[0]
        assert row.argument_summary == {
            "password": "***",
            "nested": {"token": "***"},
        }
        serialized = str(row.argument_summary) + (row.argument_hash or "")
        assert "hunter2" not in serialized
        assert "secret-token" not in serialized


def test_audit_write_failure_does_not_mask_successful_result(caplog) -> None:
    def failing_factory():
        raise OSError("audit database down")

    gateway, _loader, _sf = _gateway(repository_factory=failing_factory)

    with caplog.at_level(logging.ERROR, logger="ioc.tool_registry"):
        result = gateway.execute("query.kpi", {"a": 1}, INTERNAL)

    assert result.success is True
    assert result.data == {"total": 3}
    assert "TOOL_AUDIT_WRITE_FAILED" in caplog.text
    assert "hunter2" not in caplog.text
