from __future__ import annotations

from app.core.trace.trace_context import clear_trace_id, set_trace_id
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_registry.contracts import ActionPhase, GovernanceDecision, ToolType

from tests.tool_registry._helpers import (
    build_gateway,
    make_sqlite_session_factory,
    make_definition,
    make_policy,
    make_version,
)

KPI = make_definition(1, "kpi_query", "query.kpi", "KPI Query", "Returns KPI data")
KPI_VERSION = make_version(11, 1, implementation_ref="builtin.kpi_query")
KPI_POLICY = make_policy(1, 1)

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

    def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        return {"total": 3}, [], {"source": "stub"}


class StubPrepareTool(BaseTool):
    name = "work_order_draft"
    description = "Stub draft tool"

    def __init__(self, include_marker: bool = True) -> None:
        self.include_marker = include_marker
        self.calls = 0

    def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        data: dict = {"draft_id": "d1"}
        if self.include_marker:
            data["requires_human_confirmation"] = True
        return data, [], {}


class StubCommitTool(BaseTool):
    name = "work_order_commit"
    description = "Stub commit tool"

    def __init__(self) -> None:
        self.calls = 0

    def _execute(self, tool_input: BaseToolInput):
        self.calls += 1
        return {"committed": True}, [], {}


def _query_gateway(policies=()):
    return build_gateway(
        (KPI,),
        (KPI_VERSION,),
        policies or (KPI_POLICY,),
        executors={"builtin.kpi_query": StubQueryTool()},
    )


def _draft_gateway(include_marker: bool = True):
    tool = StubPrepareTool(include_marker=include_marker)
    gateway, loader, session_factory = build_gateway(
        (DRAFT_TOOL,),
        (DRAFT_VERSION,),
        (DRAFT_POLICY,),
        executors={"builtin.work_order_draft": tool},
    )
    return gateway, loader, session_factory, tool


def _commit_gateway():
    tool = StubCommitTool()
    gateway, loader, session_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": tool},
    )
    return gateway, loader, session_factory, tool


def test_gateway_executes_selected_executor_and_enriches_metadata() -> None:
    gateway, _loader, _sf = _query_gateway()

    result = gateway.execute("query.kpi", {"department": "安全环保部"}, INTERNAL)

    assert result.success is True
    assert result.data == {"total": 3}
    assert result.metadata["tool_key"] == "kpi_query"
    assert result.metadata["tool_version"] == "1.0.0"
    assert result.metadata["implementation_ref"] == "builtin.kpi_query"
    assert result.metadata["policy_id"] == 1
    assert result.metadata["selected_stable"] is True
    assert result.metadata["gray_bucket"] is None


def test_gateway_uses_context_request_id_as_canonical_trace_without_global_context() -> None:
    gateway, _loader, session_factory = _query_gateway()
    context = INTERNAL.model_copy(update={"request_id": "trace-mcp-no-global"})

    result = gateway.execute("query.kpi", {}, context)

    assert result.trace_id == "trace-mcp-no-global"
    with session_factory() as session:
        from sqlalchemy import select

        from app.tool_registry.models import ToolCallAudit

        audit = session.scalar(select(ToolCallAudit))
        assert audit is not None
        assert audit.trace_id == result.trace_id


def test_gateway_propagates_generated_trace_to_base_tool_without_global_or_request_id() -> None:
    clear_trace_id()
    gateway, _loader, session_factory = _query_gateway()

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.trace_id
    with session_factory() as session:
        from sqlalchemy import select

        from app.tool_registry.models import ToolCallAudit

        audit = session.scalar(select(ToolCallAudit))
        assert audit is not None
        assert audit.trace_id == result.trace_id


def test_commit_without_confirmation_returns_challenge() -> None:
    gateway, _loader, _sf, tool = _commit_gateway()

    result = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert result.metadata["confirmation_token"]
    assert tool.calls == 0


def test_commit_with_verified_confirmation_executes() -> None:
    gateway, _loader, _sf, tool = _commit_gateway()
    set_trace_id("trace-commit-1")
    try:
        first = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL)
        token = first.metadata["confirmation_token"]

        second = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert second.success is True
    assert second.metadata["tool_key"] == "work_order_commit"
    assert tool.calls == 1


def test_commit_confirmation_is_consumed_once_across_gateway_instances() -> None:
    tool = StubCommitTool()
    gateway_one, _loader, session_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": tool},
    )
    gateway_two, _loader_two, _same_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": tool},
        session_factory=session_factory,
        seed_registry_rows=False,
    )
    set_trace_id("trace-commit-single-use")
    try:
        challenge = gateway_one.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
        )
        token = challenge.metadata["confirmation_token"]
        committed = gateway_one.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
        replayed = gateway_two.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert committed.success is True
    assert replayed.success is False
    assert replayed.error is not None
    assert replayed.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert tool.calls == 1


def test_commit_confirmation_padding_variants_cannot_bypass_single_consumption() -> None:
    gateway, _loader, _session_factory, tool = _commit_gateway()
    set_trace_id("trace-commit-canonical")
    try:
        challenge = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
        )
        token = challenge.metadata["confirmation_token"]
        payload, signature = token.split(".")
        equivalent_padding_variants = (
            f"{payload}=.{signature}",
            f"{payload}.{signature}=",
            f"{payload}=.{signature}=",
        )

        results = [
            gateway.execute(
                "action.work_order.commit",
                {"draft_id": "d1"},
                INTERNAL,
                confirmation_token=candidate,
            )
            for candidate in (token, *equivalent_padding_variants)
        ]
    finally:
        clear_trace_id()

    assert results[0].success is True
    assert all(result.success is False for result in results[1:])
    assert all(
        result.error is not None and result.error.code == "TOOL_CONFIRMATION_REQUIRED"
        for result in results[1:]
    )
    assert tool.calls == 1


def test_confirmation_consumption_rollback_allows_same_token_one_retry() -> None:
    from app.tool_registry.repository import ToolRegistryRepository

    tool = StubCommitTool()
    failure_state = {"remaining": 1}
    session_factory = make_sqlite_session_factory()

    class FailFirstConfirmedAuditRepository(ToolRegistryRepository):
        def append_audit(self, audit):
            created = super().append_audit(audit)
            if audit.confirmation_token_hash and failure_state["remaining"]:
                failure_state["remaining"] -= 1
                raise OSError("simulated transaction failure")
            return created

    gateway, _loader, _same_factory = build_gateway(
        (COMMIT_TOOL,),
        (COMMIT_VERSION,),
        (COMMIT_POLICY,),
        executors={"builtin.work_order_commit": tool},
        session_factory=session_factory,
        repository_factory=lambda: FailFirstConfirmedAuditRepository(
            session_factory()
        ),
    )
    set_trace_id("trace-confirmation-rollback")
    try:
        challenge = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
        )
        token = challenge.metadata["confirmation_token"]
        failed = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
        retried = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d1"},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert failed.success is False
    assert failed.error is not None
    assert failed.error.code == "TOOL_REGISTRY_CONFIGURATION_ERROR"
    assert retried.success is True
    assert tool.calls == 1


def test_commit_confirmation_rejects_tampered_arguments() -> None:
    gateway, _loader, _sf, tool = _commit_gateway()
    set_trace_id("trace-commit-2")
    try:
        first = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL)
        token = first.metadata["confirmation_token"]

        tampered = gateway.execute(
            "action.work_order.commit",
            {"draft_id": "d2"},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert tampered.success is False
    assert tampered.error is not None
    assert tampered.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert tool.calls == 0


def test_prepare_action_executes_without_preconfirmation() -> None:
    gateway, _loader, _sf, tool = _draft_gateway()

    result = gateway.execute("action.work_order.draft", {"zone": "A"}, INTERNAL)

    assert result.success is True
    assert result.data == {"draft_id": "d1", "requires_human_confirmation": True}
    assert result.data["requires_human_confirmation"] is True
    assert result.metadata["implementation_ref"] == "builtin.work_order_draft"
    assert tool.calls == 1


def test_prepare_without_confirmation_marker_is_configuration_error() -> None:
    gateway, _loader, _sf, _tool = _draft_gateway(include_marker=False)

    result = gateway.execute("action.work_order.draft", {"zone": "A"}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_REGISTRY_CONFIGURATION_ERROR"


def test_rate_limit_blocks_beyond_limit() -> None:
    limited_policy = make_policy(9, 1, rate_limit_per_minute=2)
    gateway, _loader, _sf = _query_gateway(policies=(limited_policy,))

    assert gateway.execute("query.kpi", {}, INTERNAL).success is True
    assert gateway.execute("query.kpi", {}, INTERNAL).success is True
    blocked = gateway.execute("query.kpi", {}, INTERNAL)

    assert blocked.success is False
    assert blocked.error is not None
    assert blocked.error.code == "TOOL_RATE_LIMITED"
    assert blocked.error.detail is not None
    assert blocked.error.detail["retry_after_seconds"] >= 1
    assert blocked.metadata["tool_key"] == "kpi_query"


def test_query_policy_confirmation_returns_challenge() -> None:
    confirmation_policy = make_policy(9, 1, requires_confirmation=True)
    gateway, _loader, _sf = _query_gateway(policies=(confirmation_policy,))
    set_trace_id("trace-query-confirm")
    try:
        first = gateway.execute("query.kpi", {"a": 1}, INTERNAL)

        token = first.metadata["confirmation_token"]
        second = gateway.execute(
            "query.kpi",
            {"a": 1},
            INTERNAL,
            confirmation_token=token,
        )
    finally:
        clear_trace_id()

    assert first.success is False
    assert first.error is not None
    assert first.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert second.success is True


def test_denied_policy_returns_forbidden() -> None:
    deny = make_policy(2, 1, decision=GovernanceDecision.DENY)
    gateway, _loader, _sf = _query_gateway(policies=(deny,))

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_FORBIDDEN"


def test_unknown_capability_returns_unavailable() -> None:
    gateway, _loader, _sf = _query_gateway()

    result = gateway.execute("query.unknown", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_CAPABILITY_UNAVAILABLE"


def test_missing_executor_returns_configuration_error() -> None:
    gateway, _loader, _sf = build_gateway(
        (KPI,),
        (KPI_VERSION,),
        (KPI_POLICY,),
        executors={},
    )

    result = gateway.execute("query.kpi", {}, INTERNAL)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_REGISTRY_CONFIGURATION_ERROR"


def test_stable_only_forwards_to_registry() -> None:
    gray_version = make_version(
        12,
        1,
        version="1.1.0",
        implementation_ref="builtin.kpi_query.v110",
        is_stable=False,
        gray_percentage=100,
    )
    gray_policy = make_policy(2, 1, version_id=12, gray_percentage=100)
    gateway, _loader, _sf = build_gateway(
        (KPI,),
        (KPI_VERSION, gray_version),
        (KPI_POLICY, gray_policy),
        executors={
            "builtin.kpi_query": StubQueryTool(),
            "builtin.kpi_query.v110": StubQueryTool(),
        },
    )

    stable_result = gateway.execute("query.kpi", {}, INTERNAL, stable_only=True)

    assert stable_result.success is True
    assert stable_result.metadata["selected_stable"] is True
    assert stable_result.metadata["tool_version"] == "1.0.0"
