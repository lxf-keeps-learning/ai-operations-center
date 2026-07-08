"""合并报告 evidence 和 RAG 检索结果，形成统一上下文。

职责边界（Sprint6）：
  只负责合并上下文，不查询 RAG，不生成回答。

运行时机：紧接在 CallRagNode 之后，此时 State 中已有：
  - retrieved_context（报告 evidence 检索结果）
  - evidence_refs（报告证据引用 ID）
  - rag_results（RAG 检索结果）
  - rag_source_refs（RAG 知识来源 ID）
  - used_rag（本轮是否实际使用了 RAG）

核心设计原则：
  1. 来源不混淆：每条 merged_context 记录必须带 source_type。
  2. 报告依据始终在前，RAG 补充在后。
  3. RAG 只作为补充，不覆盖报告结论。
  4. 无论 used_rag 是否 true，都尝试合并（方便兜底场景）。
  5. 不修改 retrieved_context 和 rag_results 原始字段。
"""

from typing import Any

from app.report_chat_agent.state import ReportChatState


def merge_context_node(state: ReportChatState) -> ReportChatState:
    """合并报告 evidence 和 RAG 检索结果。

    merged_context 数组中的每一项包含 source_type 标识，
      - "report_evidence": 来自当前报告 evidence 检索。
      - "rag": 来自外部 RAG 知识库检索。

    Args:
        state: 当前 State，应包含 retrieved_context 和 rag_results。

    Returns:
        更新了 merged_context 的 State。
    """
    retrieved_context = state.get("retrieved_context", [])
    rag_results = state.get("rag_results", [])

    merged: list[dict[str, Any]] = []

    # 1. 报告 evidence（优先）。
    for item in retrieved_context:
        merged.append(_to_report_evidence(item))

    # 2. RAG 检索结果（补充）。
    used_rag = state.get("used_rag", False)
    if used_rag and rag_results:
        for item in rag_results:
            rag_entry = _to_rag_entry(item)
            if rag_entry:
                merged.append(rag_entry)

    state["merged_context"] = merged
    return state


def _to_report_evidence(item: dict) -> dict[str, Any]:
    refs = item.get("evidence_refs", [])
    source_id = refs[0] if isinstance(refs, list) and refs else ""
    return {
        "source_type": "report_evidence",
        "source_id": source_id,
        "title": item.get("title", ""),
        "content": item.get("content", ""),
        "type": item.get("type", ""),
    }


def _to_rag_entry(item: dict) -> dict[str, Any] | None:
    """把 RAG result 转为统一格式。"""
    source_id = item.get("source_id", "")
    if not source_id:
        return None
    return {
        "source_type": "rag",
        "source_id": source_id,
        "document_title": item.get("document_title", ""),
        "content": item.get("content", ""),
        "score": item.get("score"),
        "metadata": item.get("metadata", {}),
    }
