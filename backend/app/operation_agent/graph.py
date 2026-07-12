"""
Operation Graph — 运营分析智能体的编排核心。

使用 LangGraph StateGraph 编排 6 个分析节点，形成一个线性执行流水线：

  START → init_context → query_operation_data → detect_abnormal
    → analyze_reason → generate_advice → summary → END

每个节点接收 OperationState 并返回更新后的 OperationState。
State 是模块间传递数据的唯一契约，节点之间不直接调用。
"""
from collections.abc import Callable
from itertools import pairwise

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph, START

from app.operation_agent.nodes.analyze_reason_node import analyze_reason_node
from app.operation_agent.nodes.detect_abnormal_node import detect_abnormal_node
from app.operation_agent.nodes.generate_advice_node import generate_advice_node
from app.operation_agent.nodes.init_context_node import init_context_node
from app.operation_agent.nodes.query_operation_data_node import query_operation_data_node
from app.operation_agent.nodes.summary_node import summary_node
from app.operation_agent.state import OperationState


OperationNode = Callable[[OperationState], OperationState]

# 同步 Graph 和 SSE runner 共用这一份节点定义，避免新增、删除或重排节点时
# 两条执行链发生静默漂移。
OPERATION_NODE_SPECS: tuple[tuple[str, str, OperationNode], ...] = (
    ("init_context", "初始化环境", init_context_node),
    ("query_operation_data", "运营数据查询", query_operation_data_node),
    ("detect_abnormal", "异常识别", detect_abnormal_node),
    ("analyze_reason", "原因分析", analyze_reason_node),
    ("generate_advice", "建议动作生成", generate_advice_node),
    ("summary", "报告汇总", summary_node),
)

# 节点名称与消息映射，供 Adapter 和前端使用
NODE_METADATA: dict[str, dict[str, str]] = {
    node_key: {
        "name": node_name,
        "message_started": f"{node_name}中",
        "message_completed": f"{node_name}完成",
    }
    for node_key, node_name, _ in OPERATION_NODE_SPECS
}


def _with_stream_events(
    node_key: str,
    node_name: str,
    node_func: OperationNode,
) -> OperationNode:
    """包装节点函数，在节点开始执行时发射 node_started 自定义事件。

    包装器通过 get_stream_writer() 发送 LangGraph Custom Stream Event。
    该事件仅在 astream(stream_mode="custom") 时可见，invoke 时 get_stream_writer()
    返回 no-op writer，不影响同步路径。
    """
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


def build_operation_graph() -> StateGraph:
    """
    构建运营分析 Graph。

    每个节点被 _with_stream_events 包装，自动在节点入口处发射
    custom node_started 事件。

    返回一个已 compile 的 StateGraph 实例。
    该实例可以被多次 invoke / astream，每次接收一个新的 OperationState 作为输入。
    """
    graph = StateGraph(OperationState)

    for node_key, node_name, node_func in OPERATION_NODE_SPECS:
        graph.add_node(
            node_key,
            _with_stream_events(node_key, node_name, node_func),
        )

    node_keys = [node_key for node_key, _node_name, _node_func in OPERATION_NODE_SPECS]
    graph.add_edge(START, node_keys[0])
    for current_node, next_node in pairwise(node_keys):
        graph.add_edge(current_node, next_node)
    graph.add_edge(node_keys[-1], END)

    return graph.compile()


# 进程级单例 Graph 实例，在服务启动时构建，供 service 层调用
operation_graph = build_operation_graph()
