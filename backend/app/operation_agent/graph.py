"""
Operation Graph — 运营分析智能体的编排核心。

使用 LangGraph StateGraph 编排 6 个分析节点，形成一个线性执行流水线：

  START → init_context → query_operation_data → detect_abnormal
    → analyze_reason → generate_advice → summary → END

每个节点接收 OperationState 并返回更新后的 OperationState。
State 是模块间传递数据的唯一契约，节点之间不直接调用。
"""
from langgraph.graph import END, StateGraph, START

from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.detect_abnormal_node import detect_abnormal_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.nodes.init_context_node import init_context_node
from app.operation_agent.nodes.query_operation_data_node import query_operation_data_node
from app.operation_agent.nodes.summary_node import summary_node
from app.operation_agent.state import OperationState


def build_operation_graph() -> StateGraph:
    """
    构建运营分析 Graph。

    返回一个已 compile 的 StateGraph 实例。
    该实例可以被多次 invoke，每次接收一个新的 OperationState 作为输入。
    """
    graph = StateGraph(OperationState)

    # 注册 6 个节点（每个节点都是一个接收 state 并返回 state 的函数）
    graph.add_node("init_context", init_context_node)
    graph.add_node("query_operation_data", query_operation_data_node)
    graph.add_node("detect_abnormal", detect_abnormal_node)
    graph.add_node("analyze_reason", analyze_reason_node)
    graph.add_node("generate_advice", generate_advice_node)
    graph.add_node("summary", summary_node)

    # 定义执行顺序（当前为线性流程，后续可按需增加条件分支）
    graph.add_edge(START, "init_context")
    graph.add_edge("init_context", "query_operation_data")
    graph.add_edge("query_operation_data", "detect_abnormal")
    graph.add_edge("detect_abnormal", "analyze_reason")
    graph.add_edge("analyze_reason", "generate_advice")
    graph.add_edge("generate_advice", "summary")
    graph.add_edge("summary", END)

    return graph.compile()


# 进程级单例 Graph 实例，在服务启动时构建，供 service 层调用
operation_graph = build_operation_graph()
