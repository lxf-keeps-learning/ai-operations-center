"""Reusable LangGraph subgraphs for business-domain operation agents."""

import inspect
from collections.abc import Awaitable, Callable
from functools import cache

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.operation_agent.multi_agent.agents import DomainAgentSpec
from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.state import OperationState

OperationNode = Callable[[OperationState], OperationState | Awaitable[OperationState]]


def _with_stream_events(
    node_key: str,
    node_name: str,
    agent_key: str,
    node_func: OperationNode,
) -> OperationNode:
    """Expose a real domain-agent step through the established stream contract.

    与 node_func 保持相同异步性；async 包装保证取消穿透到 LLM await。
    """

    if inspect.iscoroutinefunction(node_func):
        async def wrapped_async(state: OperationState) -> OperationState:
            try:
                writer = get_stream_writer()
                writer({
                    "kind": "node_started",
                    "node_key": node_key,
                    "node_name": node_name,
                    "agent_key": agent_key,
                })
            except RuntimeError:
                pass
            return await node_func(state)

        return wrapped_async

    def wrapped(state: OperationState) -> OperationState:
        try:
            writer = get_stream_writer()
            writer({
                "kind": "node_started",
                "node_key": node_key,
                "node_name": node_name,
                "agent_key": agent_key,
            })
        except RuntimeError:
            pass
        return node_func(state)

    return wrapped


@cache
def build_domain_agent_graph(spec: DomainAgentSpec) -> CompiledStateGraph:
    """Build and cache the reason-to-advice subgraph for a domain specification."""

    graph = StateGraph(OperationState)
    reason_node = f"{spec.key}_reason"
    advice_node = f"{spec.key}_advice"

    async def run_reason(state: OperationState) -> OperationState:
        return await analyze_reason_node(
            state,
            prompt_name=spec.reason_prompt,
            action_type=spec.reason_action_type,
        )

    async def run_advice(state: OperationState) -> OperationState:
        return await generate_advice_node(
            state,
            prompt_name=spec.advice_prompt,
            action_type=spec.advice_action_type,
        )

    graph.add_node(
        reason_node,
        _with_stream_events(reason_node, f"{spec.label}原因分析", spec.key, run_reason),
    )
    graph.add_node(
        advice_node,
        _with_stream_events(advice_node, f"{spec.label}建议生成", spec.key, run_advice),
    )
    graph.add_edge(START, reason_node)
    graph.add_edge(reason_node, advice_node)
    graph.add_edge(advice_node, END)
    return graph.compile()


async def run_domain_agent(state: OperationState, spec: DomainAgentSpec) -> OperationState:
    """Run the cached domain subgraph and relay its custom events to the parent stream.

    异步执行：父图对 async 节点的取消会穿透到子图的 astream。
    """

    try:
        parent_writer = get_stream_writer()
    except RuntimeError:
        parent_writer = None

    final_state = state
    async for mode, data in build_domain_agent_graph(spec).astream(
        state,
        stream_mode=["values", "custom"],
    ):
        if mode == "values" and isinstance(data, dict):
            final_state = data
        elif mode == "custom" and parent_writer is not None:
            parent_writer(data)
    return final_state
