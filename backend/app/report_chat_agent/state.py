from typing import Any, Literal, NotRequired, TypedDict

QuestionScope = Literal[
    "report_internal",
    "report_related",
    "ioc_global",
    "out_of_scope",
]

AnswerType = Literal[
    "normal",
    "insufficient_evidence",
    "boundary",
]


class ReportChatState(TypedDict, total=False):
    trace_id: str

    report_id: str
    conversation_id: str
    session_id: str
    runtime_session_id: str
    user_id: str
    user_question: str

    scene: str
    report_context: dict[str, Any]
    report_sections: list[dict[str, Any]]
    abnormal_items: list[dict[str, Any]]
    risk_items: list[dict[str, Any]]
    advice_items: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    chat_history: list[dict[str, Any]]

    question_scope: QuestionScope
    scope_reason: str

    retrieved_context: list[dict[str, Any]]
    evidence_refs: list[str]

    need_rag: bool
    rag_reason: str

    # Sprint6.1: LLM RAG Decision fields (default absent → pure rule mode).
    rag_intent: NotRequired[str]
    rag_confidence: NotRequired[float]
    rag_decision_source: NotRequired[str]
    suggested_doc_types: NotRequired[list[str]]
    required_anchors: NotRequired[list[str]]

    rag_query: dict[str, Any]
    # Sprint6.1: LLM Query Rewrite fields (default absent → pure rule mode).
    rewritten_query: NotRequired[str]
    query_keywords: NotRequired[list[str]]
    query_rewrite_reason: NotRequired[str]
    query_rewrite_confidence: NotRequired[float]
    query_rewrite_source: NotRequired[str]

    rag_results: list[dict[str, Any]]
    rag_source_refs: list[str]
    rag_sources: NotRequired[list[dict[str, Any]]]
    used_rag: bool
    merged_context: list[dict[str, Any]]

    need_tool_query: bool
    query_scope: dict[str, Any]
    tool_results: list[dict[str, Any]]

    final_answer: str
    answer_type: AnswerType
    message_id: str
    llm_usages: list[dict[str, Any]]

    errors: list[dict[str, Any]]
