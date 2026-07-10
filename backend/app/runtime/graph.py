"""
Runtime Graph — AI Runtime 对话流程的 LangGraph 编排核心。

使用 LangGraph StateGraph 编排 4 个节点，形成一个线性执行流水线：

  START → init_session → load_prompt → call_llm → finalize → END

每个节点接收 RuntimeGraphState 并返回更新后的 RuntimeGraphState。
State 是节点间传递数据的唯一契约，节点之间不直接调用。

用法：
  from app.runtime.graph import runtime_graph
  result = runtime_graph.invoke(state)
"""

from langgraph.graph import END, StateGraph, START

from app.runtime.nodes.call_llm_node import call_llm_node
from app.runtime.nodes.finalize_node import finalize_node
from app.runtime.nodes.init_session_node import init_session_node
from app.runtime.nodes.load_prompt_node import load_prompt_node
from app.runtime.state import RuntimeGraphState


def build_runtime_graph() -> StateGraph:
    """
    构建 Runtime StateGraph。

    节点说明：
      init_session  — 校验/创建 Conversation、查询历史、创建 Session、记录 Trace
      load_prompt   — 加载 Active Prompt（可选），失败时降级为系统默认 Prompt
      call_llm      — 记录 Tool 调用、调用 LLM（支持流式/非流式）、记录 LLM Span
      finalize      — 更新 Session 状态、记录 runtime finish Span

    返回一个已 compile 的 StateGraph 实例，可多次 invoke。
    """
    graph = StateGraph(RuntimeGraphState)

    graph.add_node("init_session", init_session_node)
    graph.add_node("load_prompt", load_prompt_node)
    graph.add_node("call_llm", call_llm_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "load_prompt")
    graph.add_edge("load_prompt", "call_llm")
    graph.add_edge("call_llm", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


# 进程级单例 Graph 实例，在服务启动时构建，供 RuntimeService 调用
runtime_graph = build_runtime_graph()
