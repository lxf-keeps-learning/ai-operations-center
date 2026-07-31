"""Supervisor graph for routing operation reports through domain agents."""

from collections.abc import Callable

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.operation_agent.multi_agent.agent_graph import run_domain_agent
from app.operation_agent.multi_agent.agents import DOMAIN_AGENT_SPECS
from app.operation_agent.multi_agent.supervisor import route_domain_agent
from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.detect_abnormal_node import detect_abnormal_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.nodes.init_context_node import init_context_node
from app.operation_agent.nodes.query_operation_data_node import query_operation_data_node
from app.operation_agent.nodes.summary_node import summary_node
from app.operation_agent.state import OperationDomain, OperationState


OperationNode = Callable[[OperationState], OperationState]


def _route_supervisor_node(state: OperationState) -> OperationState:
    """Normalize the request and record the domain selected by Supervisor."""

    route_domain_agent(state)
    return state


def _dispatch_domain_agent_node(state: OperationState) -> OperationState:
    """Run the configured domain agent for the Supervisor-selected route."""

    spec = DOMAIN_AGENT_SPECS[state["supervisor_route"]]
    return run_domain_agent(state, spec)


# This contract preserves the former six metadata keys while adding the new
# parent Supervisor and domain-agent dispatch stages.
OPERATION_NODE_SPECS: tuple[tuple[str, str, OperationNode], ...] = (
    ("supervisor_route", "Supervisor 路由", _route_supervisor_node),
    ("init_context", "初始化环境", init_context_node),
    ("query_operation_data", "运营数据查询", query_operation_data_node),
    ("detect_abnormal", "异常识别", detect_abnormal_node),
    ("dispatch_domain_agent", "业务 Agent 调度", _dispatch_domain_agent_node),
    ("summary", "报告汇总", summary_node),
    ("analyze_reason", "原因分析", analyze_reason_node),
    ("generate_advice", "建议动作生成", generate_advice_node),
)

NODE_METADATA: dict[str, dict[str, str]] = {
    node_key: {
        "name": node_name,
        "message_started": f"{node_name}中",
        "message_completed": f"{node_name}完成",
    }
    for node_key, node_name, _ in OPERATION_NODE_SPECS
}
for _spec in DOMAIN_AGENT_SPECS.values():
    NODE_METADATA[f"{_spec.key}_reason"] = {
        "name": f"{_spec.label}原因分析",
        "message_started": f"{_spec.label}原因分析中",
        "message_completed": f"{_spec.label}原因分析完成",
        "agent_key": _spec.key,
    }
    NODE_METADATA[f"{_spec.key}_advice"] = {
        "name": f"{_spec.label}建议生成",
        "message_started": f"{_spec.label}建议生成中",
        "message_completed": f"{_spec.label}建议生成完成",
        "agent_key": _spec.key,
    }

_PARENT_NODE_KEYS = (
    "supervisor_route",
    "init_context",
    "query_operation_data",
    "detect_abnormal",
    "dispatch_domain_agent",
    "summary",
)
_PARENT_NODE_FUNCTIONS = {
    "supervisor_route": "_route_supervisor_node",
    "init_context": "init_context_node",
    "query_operation_data": "query_operation_data_node",
    "detect_abnormal": "detect_abnormal_node",
    "dispatch_domain_agent": "_dispatch_domain_agent_node",
    "summary": "summary_node",
}


def build_runtime_node_order(domain: OperationDomain | str | None = None) -> list[str]:
    """Return the stream sequence for one Supervisor route, ending at summary."""

    agent_key: OperationDomain
    if isinstance(domain, str) and domain in DOMAIN_AGENT_SPECS:
        agent_key = domain
    else:
        agent_key = "safety"
    return [
        *_PARENT_NODE_KEYS[:-1],
        f"{agent_key}_reason",
        f"{agent_key}_advice",
        "summary",
    ]


RUNTIME_NODE_ORDER = tuple(build_runtime_node_order())


def _with_stream_events(
    node_key: str,
    node_name: str,
    node_func: OperationNode,
) -> OperationNode:
    """Emit the established custom ``node_started`` event before a parent node."""

    def wrapped(state: OperationState) -> OperationState:
        try:
            writer = get_stream_writer()
            writer({
                "kind": "node_started",
                "node_key": node_key,
                "node_name": node_name,
            })
        except RuntimeError:
            pass
        return node_func(state)

    return wrapped


def build_supervisor_graph() -> CompiledStateGraph:
    """Build the Supervisor parent graph and its single domain-agent dispatch."""

    graph = StateGraph(OperationState)
    for node_key in _PARENT_NODE_KEYS:
        node_name = NODE_METADATA[node_key]["name"]
        node_func = globals()[_PARENT_NODE_FUNCTIONS[node_key]]
        graph.add_node(node_key, _with_stream_events(node_key, node_name, node_func))

    graph.add_edge(START, _PARENT_NODE_KEYS[0])
    for current_node, next_node in zip(_PARENT_NODE_KEYS, _PARENT_NODE_KEYS[1:]):
        graph.add_edge(current_node, next_node)
    graph.add_edge(_PARENT_NODE_KEYS[-1], END)
    return graph.compile()


supervisor_graph = build_supervisor_graph()
