import pytest

from app.operation_agent.graph import build_operation_graph, operation_graph
from app.operation_agent.multi_agent.graph import (
    NODE_METADATA,
    OPERATION_NODE_SPECS,
    build_supervisor_graph,
    supervisor_graph,
)
from app.operation_agent.nodes.init_context_node import init_context_node


def _stub_expensive_parent_nodes(monkeypatch):
    for name in (
        "query_operation_data_node",
        "detect_abnormal_node",
        "summary_node",
    ):
        monkeypatch.setattr(
            f"app.operation_agent.multi_agent.graph.{name}",
            lambda state: state,
        )
    monkeypatch.setattr(
        "app.operation_agent.multi_agent.graph.run_domain_agent",
        lambda state, _spec: state,
    )


def test_supervisor_runs_common_steps_once_and_routes_business_agent(monkeypatch):
    calls = []
    for name in (
        "init_context_node",
        "query_operation_data_node",
        "detect_abnormal_node",
        "summary_node",
    ):
        monkeypatch.setattr(
            f"app.operation_agent.multi_agent.graph.{name}",
            lambda state, _name=name: (calls.append(_name), state)[1],
        )
    monkeypatch.setattr(
        "app.operation_agent.multi_agent.graph.run_domain_agent",
        lambda state, spec: (calls.append(f"agent:{spec.key}"), state)[1],
    )

    result = build_supervisor_graph().invoke({"domain": "business", "errors": []})

    assert calls.count("init_context_node") == 1
    assert calls.count("query_operation_data_node") == 1
    assert calls.count("detect_abnormal_node") == 1
    assert calls.count("summary_node") == 1
    assert calls.count("agent:business") == 1
    assert result["supervisor_route"] == "business"


@pytest.mark.parametrize("domain", (None, "unknown"))
def test_supervisor_falls_back_to_safety_and_preserves_routing_error(monkeypatch, domain):
    _stub_expensive_parent_nodes(monkeypatch)
    state = {"errors": []}
    if domain is not None:
        state["domain"] = domain

    result = build_supervisor_graph().invoke(state)

    assert result["supervisor_route"] == "safety"
    assert result["errors"] == [
        {
            "node": "supervisor",
            "message": f"暂不支持的领域: {domain}，已回退到 safety。",
        }
    ]


def test_supervisor_routes_once_before_dispatching_domain_agent(monkeypatch):
    _stub_expensive_parent_nodes(monkeypatch)
    route_calls = []

    def route_once(state):
        route_calls.append(state.get("domain"))
        state["supervisor_route"] = "business"
        return "business"

    monkeypatch.setattr(
        "app.operation_agent.multi_agent.graph.route_domain_agent",
        route_once,
    )

    result = build_supervisor_graph().invoke({"domain": "business", "errors": []})

    assert result["supervisor_route"] == "business"
    assert route_calls == ["business"]


def test_init_context_preserves_existing_errors_and_selected_route():
    errors = [{"node": "supervisor", "message": "routing fallback"}]
    state = {"errors": errors, "supervisor_route": "business"}

    result = init_context_node(state)

    assert result["errors"] == errors
    assert result["supervisor_route"] == "business"


def test_operation_graph_compatibility_exports_supervisor_graph():
    assert operation_graph is supervisor_graph
    assert build_operation_graph() is not None


def test_supervisor_metadata_retains_the_original_six_node_keys():
    legacy_node_keys = {
        "init_context",
        "query_operation_data",
        "detect_abnormal",
        "analyze_reason",
        "generate_advice",
        "summary",
    }

    assert legacy_node_keys.issubset({key for key, _name, _node in OPERATION_NODE_SPECS})
    assert legacy_node_keys.issubset(NODE_METADATA)
