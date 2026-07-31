"""Reusable LangGraph subgraphs for business-domain operation agents."""

from functools import cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.operation_agent.multi_agent.agents import DomainAgentSpec
from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.state import OperationState


@cache
def build_domain_agent_graph(spec: DomainAgentSpec) -> CompiledStateGraph:
    """Build and cache the reason-to-advice subgraph for a domain specification."""

    graph = StateGraph(OperationState)
    reason_node = f"{spec.key}_reason"
    advice_node = f"{spec.key}_advice"

    def run_reason(state: OperationState) -> OperationState:
        return analyze_reason_node(
            state,
            prompt_name=spec.reason_prompt,
            action_type=spec.reason_action_type,
        )

    def run_advice(state: OperationState) -> OperationState:
        return generate_advice_node(
            state,
            prompt_name=spec.advice_prompt,
            action_type=spec.advice_action_type,
        )

    graph.add_node(reason_node, run_reason)
    graph.add_node(advice_node, run_advice)
    graph.add_edge(START, reason_node)
    graph.add_edge(reason_node, advice_node)
    graph.add_edge(advice_node, END)
    return graph.compile()


def run_domain_agent(state: OperationState, spec: DomainAgentSpec) -> OperationState:
    """Run the cached domain subgraph while preserving the shared operation state."""

    return build_domain_agent_graph(spec).invoke(state)
