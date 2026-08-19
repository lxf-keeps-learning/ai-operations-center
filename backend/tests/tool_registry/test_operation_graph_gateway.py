from __future__ import annotations

from app.operation_agent.nodes import query_operation_data_node as node_module
from app.operation_agent.state import OperationState
from app.tool_center.contracts import ToolContext, ToolResult


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
