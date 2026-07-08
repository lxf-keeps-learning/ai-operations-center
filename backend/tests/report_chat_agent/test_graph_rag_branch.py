"""Report Chat Graph RAG 分支集成测试。

测试重点：
  1. 报告内问题：不调用 RAG，正常回答。
  2. 制度依据问题：调用 RAG，返回 rag_source_refs。
  3. RAG 服务失败：Graph 降级，API 不报 500。
  4. 无关问题：BoundaryResponseNode 拦截，不调用 RAG。
  5. Graph 可正常 invoke，不崩溃。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.rag.schemas import RagSearchResponse, RagSearchResult
from app.report_chat_agent.graph import report_chat_graph
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult


@pytest.fixture(autouse=True)
def report_chat_graph_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Graph 集成测试只验证编排逻辑，持久化节点使用内存库避免依赖本地 MySQL。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.persist_chat_message_node.get_session_local",
        lambda: session_local,
    )

    with session_local() as db:
        yield db

    Base.metadata.drop_all(engine)


def _fake_llm(content: str = "测试回答") -> LlmResult:
    return LlmResult(
        content=content,
        model="deepseek-chat",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        success=True,
        cost_ms=100,
    )


def _fake_rag_response(results: list[dict] | None = None) -> RagSearchResponse:
    items = results or [
        RagSearchResult(
            source_id="DOC_001",
            document_title="治理规范",
            content="超期缺陷应闭环整改。",
            score=0.9,
            metadata={"doc_type": "制度"},
        ),
    ]
    return RagSearchResponse(success=True, results=items, total=len(items))


class TestGraphRagBranch:
    """Graph RAG 分支集成测试。"""

    def test_report_internal_skips_rag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """报告内问题 → 不调用 RAG → used_rag=False。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kw: _fake_llm("根据当前报告，该风险排第一。"),
        )

        state: ReportChatState = {
            "trace_id": "test_skip_rag",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "为什么这个风险排第一？",
            "scene": "essential_safety",
            "report_context": {"summary": "高风险报告", "title": "安全报告", "domain": "safety"},
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
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        result = report_chat_graph.invoke(state)

        assert result.get("used_rag") is False
        assert result.get("final_answer")
        assert result.get("rag_source_refs") == []

    def test_zhidu_wenti_triggers_rag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """制度依据问题 → 调用 RAG → used_rag=True → 返回 rag_source_refs。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kw: _fake_llm("根据当前报告和知识库规..."),
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_rag_response(),
        )

        state: ReportChatState = {
            "trace_id": "test_rag_trigger",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "这个判断有没有制度依据？",
            "scene": "essential_safety",
            "report_context": {"summary": "高风险报告", "title": "安全报告", "domain": "safety"},
            "report_sections": [],
            "abnormal_items": [{"title": "超期缺陷", "metric_name": "defect_rate"}],
            "risk_items": [],
            "advice_items": [],
            "evidence": [],
            "chat_history": [],
            "question_scope": "report_internal",
            "scope_reason": "",
            "retrieved_context": [],
            "evidence_refs": [],
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        result = report_chat_graph.invoke(state)

        assert result.get("used_rag") is True
        assert len(result.get("rag_source_refs", [])) > 0
        assert "DOC_001" in result.get("rag_source_refs", [])
        assert result.get("final_answer")

    def test_report_related_history_question_triggers_rag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """report_related 的历史案例/整改问题仍能进入 RAG 分支。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kw: _fake_llm("根据报告和历史案例回答。"),
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_rag_response(),
        )

        state: ReportChatState = {
            "trace_id": "test_related_rag_trigger",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "以前类似问题怎么整改的？",
            "scene": "essential_safety",
            "report_context": {"summary": "高风险报告", "title": "安全报告", "domain": "safety"},
            "report_sections": [],
            "abnormal_items": [{"title": "超期缺陷", "metric_name": "defect_rate"}],
            "risk_items": [],
            "advice_items": [],
            "evidence": [],
            "chat_history": [],
            "question_scope": "report_internal",
            "scope_reason": "",
            "retrieved_context": [],
            "evidence_refs": [],
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        result = report_chat_graph.invoke(state)

        assert result.get("question_scope") == "report_related"
        assert result.get("used_rag") is True
        assert result.get("rag_source_refs") == ["DOC_001"]

    def test_rule_question_triggers_rag_and_returns_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """用户询问本质安全判断规则 → 走 RAG，返回知识库依据明细。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kw: _fake_llm("根据知识库中的本质安全判断规则回答。"),
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: _fake_rag_response([
                RagSearchResult(
                    source_id="DOC_REG_006",
                    document_title="本质安全判断规则与分级标准",
                    content="本质安全判断应遵循风险分级规则。",
                    score=0.95,
                    metadata={"doc_type": "制度", "source": "安全管理制度库"},
                ),
            ]),
        )

        state: ReportChatState = {
            "trace_id": "test_rule_rag_trigger",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "这次能查到本质安全判断的规则不",
            "scene": "essential_safety",
            "report_context": {"summary": "本报告只包含本次风险结论。", "title": "安全报告", "domain": "safety"},
            "report_sections": [],
            "abnormal_items": [{"title": "本质安全高风险项"}],
            "risk_items": [],
            "advice_items": [],
            "evidence": [],
            "chat_history": [],
            "question_scope": "report_internal",
            "scope_reason": "",
            "retrieved_context": [],
            "evidence_refs": [],
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "rag_sources": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        result = report_chat_graph.invoke(state)

        assert result.get("question_scope") == "report_related"
        assert result.get("used_rag") is True
        assert result.get("rag_source_refs") == ["DOC_REG_006"]
        assert result.get("rag_sources", [])[0]["document_title"] == "本质安全判断规则与分级标准"

    def test_rag_failure_does_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RAG 服务失败 → Graph 不崩溃，used_rag=False，正常回答。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.generate_report_answer_node.llm_client.chat",
            lambda **kw: _fake_llm("根据当前报告回答。"),
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            lambda _req: RagSearchResponse(success=False, results=[], total=0, error_message="RAG 超时"),
        )

        state: ReportChatState = {
            "trace_id": "test_rag_fail",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "这个异常的制度依据是什么？",
            "scene": "essential_safety",
            "report_context": {"summary": "高风险", "title": "安全报告", "domain": "safety"},
            "report_sections": [],
            "abnormal_items": [{"title": "超期缺陷"}],
            "risk_items": [],
            "advice_items": [],
            "evidence": [],
            "chat_history": [],
            "question_scope": "report_internal",
            "scope_reason": "",
            "retrieved_context": [{"type": "abnormal_item", "title": "超期缺陷", "content": "高风险"}],
            "evidence_refs": ["EV_001"],
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        # Graph 不应崩溃。
        result = report_chat_graph.invoke(state)

        assert result.get("used_rag") is False
        assert result.get("final_answer")
        # RAG 失败应记录 errors。
        has_rag_error = any(e.get("node") == "call_rag" for e in result.get("errors", []))
        assert has_rag_error

    def test_out_of_scope_does_not_call_rag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无关问题 → BoundaryResponseNode 拦截 → 不调用 RAG。"""
        def rag_should_not_be_called(*args: object, **kwargs: object) -> object:
            msg = "RAG 不应在无关问题上被调用"
            raise RuntimeError(msg)

        monkeypatch.setattr(
            "app.report_chat_agent.nodes.call_rag_node.rag_service.retrieve",
            rag_should_not_be_called,
        )

        state: ReportChatState = {
            "trace_id": "test_out_of_scope",
            "report_id": "1",
            "session_id": "test_session",
            "user_id": "tester",
            "user_question": "帮我写首诗",
            "scene": "essential_safety",
            "report_context": {"summary": "高风险", "title": "安全报告", "domain": "safety"},
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
            "need_rag": False,
            "rag_reason": "",
            "rag_query": {},
            "rag_results": [],
            "rag_source_refs": [],
            "used_rag": False,
            "merged_context": [],
            "need_tool_query": False,
            "query_scope": {},
            "tool_results": [],
            "final_answer": "",
            "answer_type": "normal",
            "message_id": "",
            "llm_usages": [],
            "errors": [],
        }

        result = report_chat_graph.invoke(state)

        assert result.get("used_rag") is False
        assert "无关" in result.get("final_answer", "") or "当前" in result.get("final_answer", "")
