"""Compatibility exports for the Supervisor-based operation graph."""

from langgraph.graph.state import CompiledStateGraph

from app.operation_agent.multi_agent.graph import (
    NODE_METADATA,
    OPERATION_NODE_SPECS,
    build_supervisor_graph,
    supervisor_graph,
)


def build_operation_graph() -> CompiledStateGraph:
    """Build a Supervisor graph through the legacy public entry point."""

    return build_supervisor_graph()


operation_graph = supervisor_graph
