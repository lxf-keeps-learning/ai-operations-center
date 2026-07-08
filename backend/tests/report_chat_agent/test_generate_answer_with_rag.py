"""GenerateReportAnswerNode 在 RAG 场景下的单元测试。

测试重点：
  1. used_rag=True 时选择 rag_answer.md 模板。
  2. used_rag=False 时继续使用 report_answer.md（兼容 Sprint5）。
  3. RAG 增强回答中包含知识库补充依据结构。
  4. LLM 失败时走兜底 fallback。
  5. 原有报告回答不受影响。
"""

from typing import Any

import pytest

from app.report_chat_agent.nodes.generate_report_answer_node import generate_report_answer_node
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult


def _fake_llm_result(content: str = "测试回答内容", success: bool = True) -> LlmResult:
    return LlmResult(
        content=content,
        model="deepseek-chat",
        prompt_tokens=50,
        completion_tokens=20,
        total_tokens=70,
        success=success,
        error_message=None,
        cost_ms=100,
    )


def _base_state(
    question: str = "怎么处理超期缺陷？",
    used_rag: bool = False,
    rag_results: list[dict] | None = None,
    merged_context: list[dict] | None = None,
    retrieved_context: list[dict] | None = None,
    evidence_refs: list[str] | None = None,
    errors: list[dict] | None = None,
) -> ReportChatState:
    return {
        "trace_id": "trace_test_gen_rag",
        "report_id": "1",
        "session_id": "session_test",
        "user_id": "tester",
        "user_question": question,
        "scene": "essential_safety",
        "report_context": {"summary": "本次报告存在高等级风险。", "title": "本质安全分析报告"},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [{"id": "EV_001", "content": "风险排序依据..."}],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": retrieved_context or [
            {"type": "risk_item", "title": "超期缺陷风险", "content": "该风险排第一", "evidence_refs": ["EV_001"]},
        ],
        "evidence_refs": evidence_refs or ["EV_001"],
        "need_rag": used_rag,
        "rag_reason": "需要制度依据" if used_rag else "",
        "rag_query": {},
        "rag_results": rag_results or [],
        "rag_source_refs": [],
        "used_rag": used_rag,
        "merged_context": merged_context or [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "llm_usages": [],
        "errors": errors or [],
    }


class TestGenerateAnswerWithRag:
    """GenerateReportAnswerNode 在 RAG 场景下的行为测试。"""

    def test_uses_report_answer_when_no_rag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """used_rag=False → 使用 report_answer.md 模板。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kwargs: _fake_llm_result("仅基于报告的回答"),
        )

        state = _base_state(used_rag=False)
        # 捕获传入 llm_client.chat 的 user_message 来验证模板选择。
        captured: dict[str, Any] = {}

        def capturing_chat(**kwargs: Any) -> LlmResult:
            captured.update(kwargs)
            return _fake_llm_result("仅基于报告的回答")

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            capturing_chat,
        )

        result = generate_report_answer_node(state)
        user_msg = captured.get("user_message", "")
        assert result["answer_type"] == "normal"
        assert result["final_answer"] == "仅基于报告的回答"
        # 应使用 report_answer.md（其中包含"检索到的报告片段"字段）。
        assert "检索到的报告片段" in user_msg
        # 不应包含 RAG 相关字段。
        assert "RAG 检索结果" not in user_msg

    def test_uses_rag_answer_when_rag_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """used_rag=True 且 rag_results 有内容 → 使用 rag_answer.md 模板。"""
        captured: dict[str, Any] = {}

        def capturing_chat(**kwargs: Any) -> LlmResult:
            captured.update(kwargs)
            return _fake_llm_result("基于报告和知识库的回答")

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            capturing_chat,
        )

        rag_results = [
            {"source_id": "DOC_001", "document_title": "治理规范", "content": "整改要求...", "score": 0.9, "metadata": {}},
        ]
        merged_context = [
            {"source_type": "report_evidence", "source_id": "EV_001", "title": "风险", "content": "报告内容"},
            {"source_type": "rag", "source_id": "DOC_001", "document_title": "治理规范", "content": "整改要求..."},
        ]

        state = _base_state(used_rag=True, rag_results=rag_results, merged_context=merged_context)
        result = generate_report_answer_node(state)

        user_msg = captured.get("user_message", "")
        assert result["answer_type"] == "normal"
        assert result["final_answer"] == "基于报告和知识库的回答"
        # 应使用 rag_answer.md（包含"合并上下文"和"RAG 检索结果"字段）。
        assert "合并上下文" in user_msg or "RAG 检索结果" in user_msg

    def test_rag_empty_falls_back_to_report(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """used_rag=True 但 rag_results 为空 → 使用 report_answer.md 模板。"""
        captured: dict[str, Any] = {}

        def capturing_chat(**kwargs: Any) -> LlmResult:
            captured.update(kwargs)
            return _fake_llm_result("基于报告的回答")

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            capturing_chat,
        )

        state = _base_state(used_rag=True, rag_results=[])
        result = generate_report_answer_node(state)

        user_msg = captured.get("user_message", "")
        assert result["answer_type"] == "normal"
        # rag_results 为空，退化为 report_answer.md。
        assert "检索到的报告片段" in user_msg

    def test_llm_failure_fallback_includes_rag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 调用失败 → fallback 回答中包含 RAG 结果。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kwargs: _fake_llm_result("", success=False),
        )

        rag_results = [
            {"source_id": "DOC_001", "document_title": "治理规范", "content": "超期缺陷应闭环整改。"},
        ]

        state = _base_state(used_rag=True, rag_results=rag_results)
        result = generate_report_answer_node(state)

        assert result["answer_type"] == "normal"
        assert result["final_answer"]
        assert "知识库补充依据" in result["final_answer"]
        assert "治理规范" in result["final_answer"]

    def test_llm_exception_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 抛异常 → fallback 回答。"""
        def broken_chat(**kwargs: Any) -> LlmResult:
            msg = "connection error"
            raise RuntimeError(msg)

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            broken_chat,
        )

        state = _base_state(used_rag=False)
        result = generate_report_answer_node(state)

        assert result["answer_type"] == "normal"
        assert result["final_answer"]
        assert any(e["node"] == "generate_answer" for e in result["errors"])

    def test_load_report_error_skips_llm(self) -> None:
        """load_report_context 失败 → 不调用 LLM，直接返回错误提示。"""
        state = _base_state(
            errors=[{"node": "load_report_context", "message": "报告不存在"}],
        )
        state["report_context"] = {}
        result = generate_report_answer_node(state)

        assert result["answer_type"] == "insufficient_evidence"
        assert "无法加载" in result["final_answer"]

    def test_sprint5_compatibility(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sprint5 原有报告追问行为不受影响。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kwargs: _fake_llm_result("根据当前报告，该风险排第一..."),
        )

        state = _base_state(question="为什么这个风险排第一？", used_rag=False)
        result = generate_report_answer_node(state)

        assert result["answer_type"] == "normal"
        assert result["final_answer"] == "根据当前报告，该风险排第一..."
        assert result.get("used_rag") is False
