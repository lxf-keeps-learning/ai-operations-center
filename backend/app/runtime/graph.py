"""
Runtime Graph — AI Runtime 对话流程的 LangGraph 编排核心。

使用 LangGraph StateGraph 编排 4 个节点，形成一个线性执行流水线：

  START → init_session → load_prompt → call_llm → finalize → END

每个节点接收 RuntimeGraphState 并返回更新后的 RuntimeGraphState。
State 是节点间传递数据的唯一契约，节点之间不直接调用。

用法：
  from app.runtime.graph import runtime_graph
  result = runtime_graph.invoke(state)
  async for mode, data in runtime_graph.astream(state, stream_mode=["updates","custom","values"]):
      ...
"""
from collections.abc import Callable

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph, START

from app.runtime.nodes.call_llm_node import call_llm_node
from app.runtime.nodes.finalize_node import finalize_node
from app.runtime.nodes.init_session_node import init_session_node
from app.runtime.nodes.load_prompt_node import load_prompt_node
from app.runtime.state import RuntimeGraphState


RuntimeNode = Callable[[RuntimeGraphState], RuntimeGraphState]

NODE_METADATA: dict[str, dict[str, str]] = {
    "init_session": {
        "name": "初始化会话",
        "message_started": "正在初始化会话",
        "message_completed": "会话初始化完成",
    },
    "load_prompt": {
        "name": "加载 Prompt",
        "message_started": "正在加载 Prompt",
        "message_completed": "Prompt 加载完成",
    },
    "call_llm": {
        "name": "LLM 调用",
        "message_started": "正在调用 LLM",
        "message_completed": "LLM 调用完成",
    },
    "finalize": {
        "name": "会话结束",
        "message_started": "正在结束会话",
        "message_completed": "会话已结束",
    },
}


def _with_stream_events(
    node_key: str,
    node_name: str,
    node_func: RuntimeNode,
) -> RuntimeNode:
    """包装节点函数，在节点入口发射 node_started 自定义事件。"""
    def wrapped(state: RuntimeGraphState) -> RuntimeGraphState:
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


def build_runtime_graph() -> StateGraph:
    """
    构建 Runtime StateGraph。

    节点说明：
      init_session  — 校验/创建 Conversation、查询历史、创建 Session、记录 Trace
      load_prompt   — 加载 Active Prompt（可选），失败时降级为系统默认 Prompt
      call_llm      — 记录 Tool 调用、调用 LLM（支持流式/非流式）、记录 LLM Span
      finalize      — 更新 Session 状态、记录 runtime finish Span

    每个节点被 _with_stream_events 包装，自动在入口处发射 custom node_started 事件。
    返回一个已 compile 的 StateGraph 实例，可多次 invoke / astream。
    """
    graph = StateGraph(RuntimeGraphState)

    for node_key, node_name in [
        ("init_session", "初始化会话"),
        ("load_prompt", "加载 Prompt"),
        ("call_llm", "LLM 调用"),
        ("finalize", "会话结束"),
    ]:
        node_func = {
            "init_session": init_session_node,
            "load_prompt": load_prompt_node,
            "call_llm": call_llm_node,
            "finalize": finalize_node,
        }[node_key]
        graph.add_node(node_key, _with_stream_events(node_key, node_name, node_func))

    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "load_prompt")
    graph.add_edge("load_prompt", "call_llm")
    graph.add_edge("call_llm", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


# 进程级单例 Graph 实例，在服务启动时构建，供 RuntimeService 调用
runtime_graph = build_runtime_graph()
