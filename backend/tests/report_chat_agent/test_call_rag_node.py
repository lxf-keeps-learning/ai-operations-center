"""CallRagNode 单元测试。

测试重点：
  1. need_rag=False 时跳过调用。
  2. RAG 正常返回结果 → rag_source_refs 正确。
  3. RAG 返回空结果 → used_rag=False + errors 记录。
  4. RAG 服务失败 → used_rag=False + errors 记录。
  5. rag_query 为空 → 跳过调用。
"""

import pytest

from app.rag.schemas import RagSearchResponse, RagSearchResult
from app.report_chat_agent.nodes.call_rag_node import call_rag_node
from app.report_chat_agent.state import ReportChatState


def _state_with_rag(
    need_rag: bool = True,
    query: str = "本质安全场景下，超期未处理缺陷的处置要求",
    rag_query_raw: dict | None = None,
) -> ReportChatState:
    return {
        "trace_id": "trace_test_call_rag",
        "report_id": "1",
        "session_id": "session_test",
        "user_id": "tester",
        "user_question": "怎么处理？",
        "scene": "essential_safety",
        "report_context": {"summary": "高等级风险。", "domain": "safety"},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_rag": need_rag,
        "rag_reason": "需要制度依据",
        "rag_query": rag_query_raw or {
            "query": query,
            "scene": "essential_safety",
            "top_k": 5,
            "filters": {"doc_type": ["制度", "标准"], "permission_scope": "current_user_allowed", "scene": "essential_safety"},
        },
        "rag_results": [],
        "rag_source_refs": [],
        "used_rag": False,
        "merged_context": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "llm_usages": [],
        "errors": [],
    }


def _fake_success_response() -> RagSearchResponse:
    return RagSearchResponse(
        success=True,
        results=[
            RagSearchResult(
                source_id="DOC_001_CHUNK_003",
                document_title="本质安全隐患治理规范",
                content="对于超期未处理缺陷，应按照隐患等级进行闭环整改。",
                score=0.92,
                metadata={"doc_type": "制度", "version": "2026"},
            ),
            RagSearchResult(
                source_id="DOC_002_CHUNK_008",
                document_title="缺陷闭环管理制度",
                content="缺陷整改完成后需由安全部门验收确认。",
                score=0.85,
                metadata={"doc_type": "制度"},
            ),
        ],
        total=2,
    )


def _fake_empty_response() -> RagSearchResponse:
    return RagSearchResponse(success=True, results=[], total=0)


def _fake_failure_response() -> RagSearchResponse:
    return RagSearchResponse(
        success=False,
        results=[],
        total=0,
        error_message="RAG 服务超时",
    )


class TestCallRagNode:
    """CallRagNode 的各类场景测试。"""

    def test_skips_when_need_rag_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """need_rag=False 时，不调用 RagService。"""
        def never_called(*args: object, **kwargs: object) -> object:
            msg = "不应被调用"
            raise RuntimeError(msg)

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service",
            never_called,  # type: ignore[arg-type]
        )

        state = _state_with_rag(need_rag=False)
        result = call_rag_node(state)

        assert result["rag_results"] == []
        assert result["rag_source_refs"] == []
        assert result["used_rag"] is False

    def test_skips_when_rag_query_empty(self) -> None:
        """rag_query 为空时跳过调用，errors 记录。"""
        state = _state_with_rag(need_rag=True, rag_query_raw={"query": "", "scene": None, "top_k": 5, "filters": {}})
        result = call_rag_node(state)

        assert result["rag_results"] == []
        assert result["used_rag"] is False
        assert any(e["node"] == "call_rag" for e in result["errors"])

    def test_returns_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 正常返回结果 → rag_source_refs 正确。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_success_response(),
        )

        state = _state_with_rag()
        result = call_rag_node(state)

        assert result["used_rag"] is True
        assert len(result["rag_results"]) == 2
        assert result["rag_source_refs"] == ["DOC_001_CHUNK_003", "DOC_002_CHUNK_008"]
        assert result["rag_results"][0]["source_id"] == "DOC_001_CHUNK_003"
        assert result["rag_results"][0]["document_title"] == "本质安全隐患治理规范"
        assert result["rag_results"][0]["score"] == 0.92

    def test_empty_results_does_not_fabricate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 返回空结果 → used_rag=False，不编造。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_empty_response(),
        )

        state = _state_with_rag()
        result = call_rag_node(state)

        assert result["used_rag"] is False
        assert result["rag_results"] == []
        assert result["rag_source_refs"] == []
        assert any(e["node"] == "call_rag" for e in result["errors"])
        assert any("无结果" in e["message"] for e in result["errors"] if e["node"] == "call_rag")

    def test_failure_does_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 服务失败 → Graph 不崩溃，errors 记录。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_failure_response(),
        )

        state = _state_with_rag()
        result = call_rag_node(state)

        assert result["used_rag"] is False
        assert result["rag_results"] == []
        assert result["rag_source_refs"] == []
        assert any(e["node"] == "call_rag" for e in result["errors"])

    def test_rag_success_with_one_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 返回单条结果。"""
        def fake_retrieve(_req: object) -> RagSearchResponse:
            return RagSearchResponse(
                success=True,
                results=[
                    RagSearchResult(
                        source_id="DOC_001",
                        document_title="测试文档",
                        content="测试内容",
                        score=0.9,
                        metadata={},
                    ),
                ],
                total=1,
            )

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            fake_retrieve,
        )

        state = _state_with_rag()
        result = call_rag_node(state)

        assert result["used_rag"] is True
        assert len(result["rag_results"]) == 1
        assert result["rag_source_refs"] == ["DOC_001"]
        # 成功时不写 errors。
        assert not any(e["node"] == "call_rag" for e in result["errors"])

    def test_used_rag_false_when_service_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 服务不可用 → used_rag=False。"""
        def fake_retrieve(_req: object) -> RagSearchResponse:
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message="RAG 服务连接失败",
            )

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            fake_retrieve,
        )

        state = _state_with_rag()
        result = call_rag_node(state)

        assert result["used_rag"] is False
        assert result["rag_results"] == []
