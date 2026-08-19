from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config.settings import settings
from app.main import app
from app.operation_agent.nodes import query_operation_data_node as node_module
from app.operation_agent.state import OperationState
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, ToolContext, ToolResult
from app.tool_registry import compat
from app.tool_registry.contracts import GovernanceDecision, ToolType
from app.tool_registry.models import ToolCallAudit

from tests.tool_registry._helpers import build_gateway, make_definition, make_policy, make_version


def _safety_state() -> OperationState:
    return {
        "trigger_type": "tab_analysis",
        "user_question": None,
        "user_context": {"user_id": "demo_user", "role": "operation_manager"},
        "page_context": {
            "domain": "safety",
            "active_tab": "本质安全",
            "time_dimension": "month",
            "date": "2026-07",
        },
    }


def test_query_node_uses_capabilities(monkeypatch) -> None:
    calls: list[str] = []

    def fake_execute(
        capability: str,
        arguments: dict,
        context: ToolContext,
        confirmation_token: str | None = None,
        stable_only: bool = False,
    ) -> ToolResult:
        calls.append(capability)
        return ToolResult(
            success=True,
            data={"items": [], "total": 0},
            metadata={"tool_key": capability.rsplit(".", 1)[-1], "tool_version": "1.0.0"},
        )

    monkeypatch.setattr(node_module, "execute_tool", fake_execute)

    node_module.query_operation_data_node(_safety_state())

    assert calls == [
        "query.kpi",
        "query.alarm",
        "query.risk",
        "query.work_order",
        "analysis.ioc_summary",
    ]


def test_query_node_marks_caller_as_internal(monkeypatch) -> None:
    contexts: list[ToolContext] = []

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        contexts.append(context)
        return ToolResult(success=True, data={"items": [], "total": 0})

    monkeypatch.setattr(node_module, "execute_tool", fake_execute)

    node_module.query_operation_data_node(_safety_state())

    assert contexts
    assert all(context.caller_type == "internal" for context in contexts)


def test_query_node_uses_first_http_role(monkeypatch) -> None:
    contexts: list[ToolContext] = []

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        contexts.append(context)
        return ToolResult(success=True, data={"items": [], "total": 0})

    monkeypatch.setattr(node_module, "execute_tool", fake_execute)
    state = _safety_state()
    state["user_context"] = {"roles": ["operator", "auditor"]}

    node_module.query_operation_data_node(state)

    assert contexts
    assert all(context.role == "operator" for context in contexts)


def test_query_node_evidence_uses_selected_tool_key(monkeypatch) -> None:
    from app.tool_center.contracts import Evidence

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        if capability == "analysis.ioc_summary":
            return ToolResult(
                success=True,
                data={"risk_score": 0},
                evidence=[Evidence(source="analysis_engine", source_type="analysis")],
                metadata={"tool_key": "ioc_summary_analysis"},
            )
        return ToolResult(
            success=True,
            data={"items": [], "total": 0},
            evidence=[Evidence(source="mock_ioc_api", source_type="kpi_api")],
            metadata={"tool_key": "kpi_query", "tool_version": "1.0.0"},
        )

    monkeypatch.setattr(node_module, "execute_tool", fake_execute)

    state = _safety_state()
    node_module.query_operation_data_node(state)

    labels = {evidence["tool_name"] for evidence in state["evidence"]}
    assert labels == {"kpi_query", "ioc_summary_analysis"}


def test_query_node_skips_failed_tools_and_records_errors(monkeypatch) -> None:
    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        if capability == "query.risk":
            from app.tool_center.contracts import ToolError

            return ToolResult(
                success=False,
                error=ToolError(code="TOOL_UPSTREAM_ERROR", message="risk down"),
            )
        return ToolResult(success=True, data={"items": [], "total": 0})

    monkeypatch.setattr(node_module, "execute_tool", fake_execute)

    state = _safety_state()
    node_module.query_operation_data_node(state)

    assert any(
        error.get("node") == "query_operation_data" and "risk" in error.get("message", "")
        for error in state.get("errors", [])
    )


class _EmptyTool(BaseTool):
    name = "empty"
    description = "empty"

    def _execute(self, tool_input: BaseToolInput):
        return {"items": [], "total": 0}, [], {}


@pytest.mark.anyio
async def test_http_graph_gateway_enforces_first_role_deny(monkeypatch) -> None:
    capabilities = (
        (1, "kpi_query", "query.kpi", ToolType.QUERY),
        (2, "alarm_query", "query.alarm", ToolType.QUERY),
        (3, "risk_query", "query.risk", ToolType.QUERY),
        (4, "work_order_query", "query.work_order", ToolType.QUERY),
        (5, "ioc_summary_analysis", "analysis.ioc_summary", ToolType.ANALYSIS),
    )
    definitions = tuple(
        make_definition(tool_id, tool_key, capability, tool_type=tool_type)
        for tool_id, tool_key, capability, tool_type in capabilities
    )
    versions = tuple(
        make_version(tool_id * 10 + 1, tool_id, implementation_ref=f"builtin.{tool_key}")
        for tool_id, tool_key, _capability, _tool_type in capabilities
    )
    policies = [make_policy(tool_id * 10, tool_id) for tool_id, *_rest in capabilities]
    denied_policy = make_policy(
        99,
        1,
        tenant_id="tenant-http",
        role="operator",
        decision=GovernanceDecision.DENY,
    )
    policies.append(denied_policy)
    executors = {
        f"builtin.{tool_key}": _EmptyTool()
        for _tool_id, tool_key, _capability, _tool_type in capabilities
    }
    gateway, _loader, session_factory = build_gateway(
        definitions,
        versions,
        tuple(policies),
        executors=executors,
    )
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    monkeypatch.setattr(compat, "get_tool_gateway", lambda: gateway)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/operation/analyze",
            headers={
                "X-Trace-Id": "trace-http-role-deny",
                "X-User-Id": "operator-1",
                "X-Org-Id": "tenant-http",
                "X-Roles": "operator,auditor",
            },
            json={"domain": "safety", "force_refresh": True},
        )

    assert response.status_code == 200
    assert any(
        "query.kpi" in item["message"] and "denied" in item["message"].lower()
        for item in response.json()["data"]["errors"]
    )
    with session_factory() as session:
        denied = session.scalar(
            select(ToolCallAudit).where(ToolCallAudit.decision == "denied")
        )
        assert denied is not None
        assert denied.role == "operator"
        assert denied.policy_id == denied_policy.id
