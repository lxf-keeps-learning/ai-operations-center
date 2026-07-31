import anyio
import pytest

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.langgraph_event_adapter import LangGraphEventAdapter
from app.operation_agent.graph import build_operation_graph, operation_graph
from app.operation_agent.multi_agent import agent_graph
from app.operation_agent.multi_agent.graph import (
    NODE_METADATA,
    OPERATION_NODE_SPECS,
    build_runtime_node_order,
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


def _stub_domain_agent_llm(monkeypatch):
    def fake_reason(state, **_kwargs):
        state["reason_analysis"] = "领域原因分析"
        return state

    def fake_advice(state, **_kwargs):
        state["advice_items"] = [{"title": "领域建议"}]
        return state

    monkeypatch.setattr(agent_graph, "analyze_reason_node", fake_reason)
    monkeypatch.setattr(agent_graph, "generate_advice_node", fake_advice)
    agent_graph.build_domain_agent_graph.cache_clear()


def test_compiled_supervisor_fallback_is_canonical_for_query_and_summary(monkeypatch):
    """An invalid route must not leave a conflicting page-context domain behind."""
    _stub_domain_agent_llm(monkeypatch)
    queried_domains = []

    def fake_operation_snapshot(state, _errors):
        queried_domains.append(state["page_context"]["domain"])
        state["raw_data"]["domain"] = state["page_context"]["domain"]
        state["metrics"] = []
        state["evidence"] = []

    monkeypatch.setattr(
        "app.operation_agent.nodes.query_operation_data_node._query_operation_snapshot",
        fake_operation_snapshot,
    )

    try:
        result = build_supervisor_graph().invoke(
            {
                "domain": "unsupported",
                "page_context": {"domain": "business"},
                "errors": [],
            }
        )
    finally:
        agent_graph.build_domain_agent_graph.cache_clear()

    assert result["supervisor_route"] == "safety"
    assert result["page_context"]["domain"] == "safety"
    assert queried_domains == ["safety"]
    assert result["raw_data"]["domain"] == "safety"
    assert "**本质安全**" in result["final_answer"]


def test_compiled_supervisor_streams_registered_child_agent_nodes_to_terminal_progress(monkeypatch):
    """Real domain-agent steps must be visible without exposing unknown runtime nodes."""
    _stub_domain_agent_llm(monkeypatch)

    async def collect_parts():
        parts = []
        graph = build_supervisor_graph()
        async for part in graph.astream(
            {
                "domain": "business",
                "page_context": {"domain": "business"},
                "errors": [],
            },
            stream_mode=["values", "updates", "custom"],
        ):
            parts.append(part)
        return parts

    try:
        parts = anyio.run(collect_parts)
    finally:
        agent_graph.build_domain_agent_graph.cache_clear()

    runtime_node_order = build_runtime_node_order("business")
    adapter = LangGraphEventAdapter(
        SseEventEmitter(run_id="supervisor_child_stream"),
        NODE_METADATA,
        runtime_node_order,
    )
    stream_events = []
    for mode, data in parts:
        stream_events.extend(adapter.process(mode, data))

    child_keys = ("business_reason", "business_advice")
    child_started = [
        event
        for event in stream_events
        if event["event_type"] == "node_started" and event["node_key"] in child_keys
    ]
    summary_completed = next(
        event
        for event in stream_events
        if event["event_type"] == "node_completed" and event["node_key"] == "summary"
    )

    assert set(child_keys).issubset(NODE_METADATA)
    assert [event["node_key"] for event in child_started] == list(child_keys)
    assert [event["payload"]["agent_key"] for event in child_started] == ["business", "business"]
    assert runtime_node_order[-1] == "summary"
    assert summary_completed["progress"] == 100
