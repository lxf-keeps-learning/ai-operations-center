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

    graph.add_node("load_report_context", load_report_context_wrapper)
    graph.add_node("classify_question_scope", classify_question_scope_node)
    graph.add_node("retrieve_report_evidence", retrieve_report_evidence_node)
    graph.add_node("should_use_rag", should_use_rag_node)
    graph.add_node("build_rag_query", build_rag_query_node)
    graph.add_node("call_rag", call_rag_node)
    graph.add_node("merge_context", merge_context_node)
    graph.add_node("generate_report_answer", generate_report_answer_node)
    graph.add_node("boundary_response", boundary_response_node)
    graph.add_node("persist_chat_message", persist_chat_message_node)

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

    # Sprint5 原有链路：报告检索 → RAG 判断 → (条件路由)。
    graph.add_edge("retrieve_report_evidence", "should_use_rag")

    graph.add_conditional_edges(
        "should_use_rag",
        _route_after_rag_check,
        {
            "build_rag_query": "build_rag_query",
            "generate_report_answer": "generate_report_answer",
        },
    )

    # Sprint6 新增 RAG 分支。
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
