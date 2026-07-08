"""MergeContextNode 单元测试。

测试重点：
  1. 只有报告 evidence，无 RAG。
  2. 报告 evidence + RAG results。
  3. RAG results 为空。
  4. RAG 结果缺少 source_id 时不被收录。
  5. 来源区分：report_evidence vs rag。
  6. 报告依据始终在前。
"""

from app.report_chat_agent.nodes.merge_context_node import merge_context_node
from app.report_chat_agent.state import ReportChatState


def _state_with_context(
    retrieved_context: list[dict] | None = None,
    rag_results: list[dict] | None = None,
    used_rag: bool = True,
) -> ReportChatState:
    return {
        "trace_id": "trace_test_merge",
        "report_id": "1",
        "session_id": "session_test",
        "user_id": "tester",
        "user_question": "怎么处理超期缺陷？",
        "scene": "essential_safety",
        "report_context": {"summary": "高风险报告", "domain": "safety"},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": retrieved_context or [],
        "evidence_refs": [],
        "need_rag": True,
        "rag_reason": "需要 RAG",
        "rag_query": {},
        "rag_results": rag_results or [],
        "rag_source_refs": [],
        "used_rag": used_rag,
        "merged_context": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "llm_usages": [],
        "errors": [],
    }


_SAMPLE_REPORT_EVIDENCE = [
    {"type": "risk_item", "title": "超期未处理缺陷风险", "content": "该风险因...", "evidence_refs": ["EV_001"]},
    {"type": "abnormal_item", "title": "缺陷率异常", "content": "本月缺陷率...", "evidence_refs": ["EV_002"]},
]

_SAMPLE_RAG_RESULTS = [
    {
        "source_id": "DOC_001_CHUNK_003",
        "document_title": "本质安全隐患治理规范",
        "content": "对于超期未处理缺陷，应按照隐患等级进行闭环整改。",
        "score": 0.92,
        "metadata": {"doc_type": "制度", "version": "2026"},
    },
    {
        "source_id": "DOC_002_CHUNK_008",
        "document_title": "缺陷闭环管理制度",
        "content": "缺陷整改完成后需由安全部门验收确认。",
        "score": 0.85,
        "metadata": {"doc_type": "制度"},
    },
]


class TestMergeContextNode:
    """MergeContextNode 的各类场景测试。"""

    def test_only_report_evidence(self) -> None:
        """只有报告 evidence，无 RAG → merged_context 都是 report_evidence。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE,
            used_rag=False,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert len(merged) == 2
        assert all(item["source_type"] == "report_evidence" for item in merged)

    def test_report_evidence_plus_rag(self) -> None:
        """报告 evidence + RAG results → 两者都在 merged_context 中。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE,
            rag_results=_SAMPLE_RAG_RESULTS,
            used_rag=True,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert len(merged) == 4
        # 报告依据在前。
        assert merged[0]["source_type"] == "report_evidence"
        assert merged[1]["source_type"] == "report_evidence"
        # RAG 在后。
        assert merged[2]["source_type"] == "rag"
        assert merged[3]["source_type"] == "rag"

    def test_source_type_markings(self) -> None:
        """source_type 区分 report_evidence 和 rag。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE[:1],
            rag_results=_SAMPLE_RAG_RESULTS[:1],
            used_rag=True,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert merged[0]["source_type"] == "report_evidence"
        assert merged[0]["title"] == "超期未处理缺陷风险"
        assert merged[1]["source_type"] == "rag"
        assert merged[1]["source_id"] == "DOC_001_CHUNK_003"
        assert merged[1]["document_title"] == "本质安全隐患治理规范"

    def test_rag_empty_results(self) -> None:
        """RAG 返回空结果 → merged_context 只包含报告 evidence。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE,
            rag_results=[],
            used_rag=False,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert len(merged) == 2
        assert all(item["source_type"] == "report_evidence" for item in merged)

    def test_no_evidence_no_rag(self) -> None:
        """既无报告 evidence 也无 RAG → merged_context 为空。"""
        state = _state_with_context(retrieved_context=[], rag_results=[])
        result = merge_context_node(state)
        assert result["merged_context"] == []

    def test_rag_result_without_source_id_skipped(self) -> None:
        """RAG 结果缺少 source_id → 不在 merged_context 中出现。"""
        bad_rag = [
            {"document_title": "无 source_id 文档", "content": "不应被收录", "score": 0.8},
        ]
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE[:1],
            rag_results=bad_rag,
            used_rag=True,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert len(merged) == 1
        assert merged[0]["source_type"] == "report_evidence"

    def test_report_evidence_order_preserved(self) -> None:
        """报告 evidence 保留原始顺序。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE,
            rag_results=_SAMPLE_RAG_RESULTS,
            used_rag=True,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert merged[0]["title"] == "超期未处理缺陷风险"
        assert merged[1]["title"] == "缺陷率异常"

    def test_rag_metadata_preserved(self) -> None:
        """RAG 结果的 metadata 和 score 保留。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE[:1],
            rag_results=_SAMPLE_RAG_RESULTS[:1],
            used_rag=True,
        )
        result = merge_context_node(state)
        rag_entry = result["merged_context"][1]

        assert rag_entry["score"] == 0.92
        assert rag_entry["metadata"]["doc_type"] == "制度"
        assert rag_entry["metadata"]["version"] == "2026"

    def test_used_rag_false_skips_rag_merge(self) -> None:
        """used_rag=False 时，即使 rag_results 存在也不合并。"""
        state = _state_with_context(
            retrieved_context=_SAMPLE_REPORT_EVIDENCE,
            rag_results=_SAMPLE_RAG_RESULTS,
            used_rag=False,
        )
        result = merge_context_node(state)
        merged = result["merged_context"]

        assert len(merged) == 2
        assert all(item["source_type"] == "report_evidence" for item in merged)
