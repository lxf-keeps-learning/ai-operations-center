from langgraph.graph import END, StateGraph, START

from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.detect_abnormal_node import detect_abnormal_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.nodes.init_context_node import init_context_node
from app.operation_agent.nodes.query_operation_data_node import query_operation_data_node
from app.operation_agent.nodes.summary_node import summary_node
from app.operation_agent.state import OperationState


def build_operation_graph() -> StateGraph:
    graph = StateGraph(OperationState)

    graph.add_node("init_context", init_context_node)
    graph.add_node("query_operation_data", query_operation_data_node)
    graph.add_node("detect_abnormal", detect_abnormal_node)
    graph.add_node("analyze_reason", analyze_reason_node)
    graph.add_node("generate_advice", generate_advice_node)
    graph.add_node("summary", summary_node)

    graph.add_edge(START, "init_context")
    graph.add_edge("init_context", "query_operation_data")
    graph.add_edge("query_operation_data", "detect_abnormal")
    graph.add_edge("detect_abnormal", "analyze_reason")
    graph.add_edge("analyze_reason", "generate_advice")
    graph.add_edge("generate_advice", "summary")
    graph.add_edge("summary", END)

    return graph.compile()


operation_graph = build_operation_graph()
