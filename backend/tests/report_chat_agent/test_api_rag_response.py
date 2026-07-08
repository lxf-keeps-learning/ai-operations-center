"""Report Chat API RAG 响应字段测试。

测试重点：
  1. SendMessageResponse schema 包含 used_rag 和 rag_source_refs。
  2. API 响应中 used_rag 和 rag_source_refs 正确映射。
  3. 原有 evidence_refs 保留。
  4. 响应结构兼容前端期望格式。
"""

from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.report_chat_agent.api import chat_api
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.schemas.response import SendMessageResponse


@pytest.fixture(autouse=True)
def report_chat_api_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """API 测试只验证响应契约，使用内存库替代本地 MySQL。"""
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

    def override_get_db() -> Iterator[Session]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[chat_api.get_db] = override_get_db
    monkeypatch.setattr("app.report_chat_agent.service.get_session_local", lambda: session_local)
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.persist_chat_message_node.get_session_local",
        lambda: session_local,
    )

    with session_local() as db:
        yield db

    app.dependency_overrides.pop(chat_api.get_db, None)
    Base.metadata.drop_all(engine)


class TestSendMessageResponseSchema:
    """SendMessageResponse Pydantic schema 的 RAG 字段测试。"""

    def test_schema_includes_rag_fields(self) -> None:
        """SendMessageResponse 包含 used_rag 和 rag_source_refs。"""
        resp = SendMessageResponse(
            trace_id="trace_001",
            session_id="session_001",
            message_id="msg_001",
            question_scope="report_internal",
            answer="测试回答",
            evidence_refs=["EV_001"],
            used_rag=True,
            rag_source_refs=["DOC_001"],
            rag_sources=[
                {
                    "source_id": "DOC_001",
                    "document_title": "本质安全判断规则与分级标准",
                    "metadata": {"source": "安全管理制度库"},
                },
            ],
        )

        data = resp.model_dump()
        assert data["used_rag"] is True
        assert data["rag_source_refs"] == ["DOC_001"]
        assert data["rag_sources"][0]["document_title"] == "本质安全判断规则与分级标准"
        assert data["evidence_refs"] == ["EV_001"]

    def test_schema_defaults_false_and_empty(self) -> None:
        """不传 RAG 字段时使用默认值。"""
        resp = SendMessageResponse(
            trace_id="trace_001",
            session_id="session_001",
            message_id="msg_001",
            question_scope="report_internal",
            answer="测试回答",
        )

        data = resp.model_dump()
        assert data["used_rag"] is False
        assert data["rag_source_refs"] == []
        assert data["rag_sources"] == []

    def test_schema_with_only_rag(self) -> None:
        """有 RAG 无报告证据的场景。"""
        resp = SendMessageResponse(
            trace_id="trace_001",
            session_id="session_001",
            message_id="msg_001",
            question_scope="report_internal",
            answer="知识库补充回答",
            evidence_refs=[],
            used_rag=True,
            rag_source_refs=["DOC_001", "DOC_002"],
        )

        data = resp.model_dump()
        assert data["used_rag"] is True
        assert len(data["rag_source_refs"]) == 2
        assert data["evidence_refs"] == []

    def test_schema_preserves_legacy_fields(self) -> None:
        """保留 Sprint5 原有字段。"""
        resp = SendMessageResponse(
            trace_id="trace_001",
            session_id="session_001",
            message_id="msg_001",
            question_scope="report_internal",
            answer="测试回答",
            evidence_refs=["EV_001", "EV_002"],
            query_scope={"metric": "defect_rate"},
            answer_type="normal",
        )

        data = resp.model_dump()
        assert data["trace_id"] == "trace_001"
        assert data["session_id"] == "session_001"
        assert data["message_id"] == "msg_001"
        assert data["question_scope"] == "report_internal"
        assert data["answer"] == "测试回答"
        assert data["query_scope"] == {"metric": "defect_rate"}
        assert data["answer_type"] == "normal"


@pytest.mark.anyio
async def test_report_chat_api_missing_session_returns_404() -> None:
    """发送消息时 session 不存在 → 404，不报 500。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/sessions/nonexistent_session/messages",
            json={"report_id": 999, "question": "测试问题"},
        )

        payload = response.json()
        assert response.status_code == 404
        assert payload["success"] is False


@pytest.mark.anyio
async def test_get_messages_returns_persisted_rag_refs(report_chat_api_db: Session) -> None:
    """历史消息接口应返回已持久化的 RAG 引用，支持刷新后继续展示知识库依据。"""
    session = report_chat_repo.create_session(
        report_chat_api_db,
        report_id=1,
        user_id="tester",
        session_id="session_with_rag_refs",
    )
    report_chat_repo.create_message(
        report_chat_api_db,
        session_id=session.id,
        report_id=session.report_id,
        role="assistant",
        content="根据报告和知识库回答。",
        evidence_refs=["EV_001"],
        used_rag=True,
        rag_source_refs=["DOC_001_CHUNK_003"],
        rag_sources=[
            {
                "source_id": "DOC_001_CHUNK_003",
                "document_title": "本质安全隐患治理规范",
                "content": "超期缺陷应闭环整改。",
                "metadata": {"source": "安全管理制度库", "doc_type": "制度"},
            },
        ],
        question_scope="report_internal",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sessions/session_with_rag_refs/messages")

    payload = response.json()
    assert response.status_code == 200
    message = payload["data"]["messages"][0]
    assert message["used_rag"] is True
    assert message["rag_source_refs"] == ["DOC_001_CHUNK_003"]
    assert message["rag_sources"][0]["document_title"] == "本质安全隐患治理规范"
    assert message["evidence_refs"] == ["EV_001"]


@pytest.mark.anyio
async def test_report_chat_create_session_missing_report_is_not_500() -> None:
    """创建会话时 report 不存在，不报 500。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/reports/99999/chat/sessions",
            json={"user_id": "tester"},
        )

        # 即使报告不存在，服务也会创建会话（不验证报告是否存在）。
        # 只要不返回 500 即可。
        assert response.status_code in (200, 404, 500)
        if response.status_code == 500:
            pytest.fail("创建会话时不应该返回 500")
