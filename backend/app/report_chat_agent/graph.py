"""Report Chat Graph：基于报告的 AI 会话流程编排。

Sprint5 流程（报告内追问）：
  START -> load_report_context -> classify_question_scope
    -> (report_internal) -> retrieve_report_evidence -> generate_report_answer -> persist -> END
    -> (其他) -> boundary_response -> persist -> END

Sprint6 新增 RAG 分支：
  (report_internal / report_related) -> retrieve_report_evidence -> should_use_rag
    -> (need_rag=false) -> generate_report_answer
    -> (need_rag=true) -> build_rag_query -> call_rag -> merge_context -> generate_report_answer

设计原则：
  - 不破坏原有 Sprint5 流程。
  - RAG 分支是可选的，不影响不需要 RAG 的问题。
  - 无关问题和 IOC 全局问题仍然走 boundary_response，不调用 RAG。
"""
from collections.abc import Callable

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.report_chat_agent.nodes.boundary_response_node import boundary_response_node
from app.report_chat_agent.nodes.build_rag_query_node import build_rag_query_node
from app.report_chat_agent.nodes.call_rag_node import call_rag_node
from app.report_chat_agent.nodes.classify_question_scope_node import classify_question_scope_node
from app.report_chat_agent.nodes.generate_report_answer_node import generate_report_answer_node
from app.report_chat_agent.nodes.merge_context_node import merge_context_node
from app.report_chat_agent.nodes.persist_chat_message_node import persist_chat_message_node
from app.report_chat_agent.nodes.retrieve_report_evidence_node import retrieve_report_evidence_node
from app.report_chat_agent.nodes.should_use_rag_node import should_use_rag_node
from app.report_chat_agent.state import ReportChatState


ReportChatNode = Callable[[ReportChatState], ReportChatState]

NODE_METADATA: dict[str, dict[str, str]] = {
    "load_report_context": {
        "name": "加载报告上下文",
        "message_started": "正在加载报告上下文",
        "message_completed": "报告上下文加载完成",
    },
    "classify_question_scope": {
        "name": "问题范围分类",
        "message_started": "正在分析问题范围",
        "message_completed": "问题范围分析完成",
    },
    "retrieve_report_evidence": {
        "name": "报告证据检索",
        "message_started": "正在检索报告证据",
        "message_completed": "报告证据检索完成",
    },
    "should_use_rag": {
        "name": "RAG 判断",
        "message_started": "正在判断是否需要知识库",
        "message_completed": "RAG 判断完成",
    },
    "build_rag_query": {
        "name": "构建 RAG 查询",
        "message_started": "正在构建知识库查询",
        "message_completed": "知识库查询构建完成",
    },
    "call_rag": {
        "name": "知识库检索",
        "message_started": "正在检索知识库",
        "message_completed": "知识库检索完成",
    },
    "merge_context": {
        "name": "融合上下文",
        "message_started": "正在融合报告与知识库上下文",
        "message_completed": "上下文融合完成",
    },
    "generate_report_answer": {
        "name": "生成回答",
        "message_started": "正在生成回答",
        "message_completed": "回答生成完成",
    },
    "boundary_response": {
        "name": "边界回应",
        "message_started": "正在生成边界回应",
        "message_completed": "边界回应完成",
    },
    "persist_chat_message": {
        "name": "持久化消息",
        "message_started": "正在保存消息",
        "message_completed": "消息已保存",
    },
}


def _with_stream_events(
    node_key: str,
    node_name: str,
    node_func: ReportChatNode,
) -> ReportChatNode:
    """包装节点函数，在节点入口发射 node_started 自定义事件。"""
    def wrapped(state: ReportChatState) -> ReportChatState:
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


def _route_after_classify(state: ReportChatState) -> str:
    """根据问题边界分类路由到报告检索或边界拦截。"""
    scope = state.get("question_scope", "report_internal")
    if scope in ("report_internal", "report_related"):
        return "retrieve_report_evidence"
    if scope in ("ioc_global", "out_of_scope"):
        return "boundary_response"
    return "retrieve_report_evidence"


def _route_after_rag_check(state: ReportChatState) -> str:
    """根据是否需要 RAG 路由到 RAG 分支或直接回答。"""
    if state.get("need_rag", False):
        return "build_rag_query"
    return "generate_report_answer"


def build_report_chat_graph() -> StateGraph:
    graph = StateGraph(ReportChatState)

    _NODES: list[tuple[str, str, ReportChatNode]] = [
        ("load_report_context", "加载报告上下文", load_report_context_wrapper),
        ("classify_question_scope", "问题范围分类", classify_question_scope_node),
        ("retrieve_report_evidence", "报告证据检索", retrieve_report_evidence_node),
        ("should_use_rag", "RAG 判断", should_use_rag_node),
        ("build_rag_query", "构建 RAG 查询", build_rag_query_node),
        ("call_rag", "知识库检索", call_rag_node),
        ("merge_context", "融合上下文", merge_context_node),
        ("generate_report_answer", "生成回答", generate_report_answer_node),
        ("boundary_response", "边界回应", boundary_response_node),
        ("persist_chat_message", "持久化消息", persist_chat_message_node),
    ]

    for node_key, node_name, node_func in _NODES:
        graph.add_node(node_key, _with_stream_events(node_key, node_name, node_func))

    graph.add_edge(START, "load_report_context")
    graph.add_edge("load_report_context", "classify_question_scope")

    graph.add_conditional_edges(
        "classify_question_scope",
        _route_after_classify,
        {
            "retrieve_report_evidence": "retrieve_report_evidence",
            "boundary_response": "boundary_response",
        },
    )

    graph.add_edge("retrieve_report_evidence", "should_use_rag")

    graph.add_conditional_edges(
        "should_use_rag",
        _route_after_rag_check,
        {
            "build_rag_query": "build_rag_query",
            "generate_report_answer": "generate_report_answer",
        },
    )

    graph.add_edge("build_rag_query", "call_rag")
    graph.add_edge("call_rag", "merge_context")
    graph.add_edge("merge_context", "generate_report_answer")

    graph.add_edge("generate_report_answer", "persist_chat_message")
    graph.add_edge("boundary_response", "persist_chat_message")
    graph.add_edge("persist_chat_message", END)

    return graph.compile()


def load_report_context_wrapper(state: ReportChatState) -> ReportChatState:
    from app.db.session import get_session_local

    db = get_session_local()()
    try:
        from app.report_chat_agent.nodes.load_report_context_node import load_report_context_node
        return load_report_context_node(state, db)
    finally:
        db.close()


report_chat_graph = build_report_chat_graph()
