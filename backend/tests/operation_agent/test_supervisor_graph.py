from app.operation_agent.graph import build_operation_graph, operation_graph
from app.operation_agent.multi_agent.graph import (
    NODE_METADATA,
    OPERATION_NODE_SPECS,
    build_supervisor_graph,
    supervisor_graph,
)
from app.operation_agent.nodes.init_context_node import init_context_node


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
