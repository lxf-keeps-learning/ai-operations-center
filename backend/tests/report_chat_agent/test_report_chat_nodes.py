from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.report_chat_agent.models import ReportChatMessage, ReportChatSession
from app.report_chat_agent.nodes.boundary_response_node import boundary_response_node
from app.report_chat_agent.nodes.classify_question_scope_node import classify_question_scope_node
from app.report_chat_agent.nodes.generate_report_answer_node import generate_report_answer_node
from app.report_chat_agent.nodes.persist_chat_message_node import persist_chat_message_node
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.service import send_chat_message
from app.report_chat_agent.state import ReportChatState
from app.runtime.models import AiConversation, AiSession

_REPORT_CHAT_MODELS = (ReportChatSession, ReportChatMessage)


@pytest.fixture
def report_chat_db(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
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
    monkeypatch.setattr(
        "app.report_chat_agent.service.get_session_local",
        lambda: session_local,
    )

    with session_local() as db:
        yield db

    Base.metadata.drop_all(engine)


def _base_state(question: str) -> ReportChatState:
    return {
        "trace_id": "trace_test_report_chat",
        "report_id": "1",
        "session_id": "session_test_report_chat",
        "user_id": "tester",
        "user_question": question,
        "scene": "essential_safety",
        "report_context": {"summary": "本次报告存在高等级风险。"},
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
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "llm_usages": [],
        "errors": [],
    }


@pytest.mark.anyio
async def test_classify_report_internal_question() -> None:
    state = classify_question_scope_node(_base_state("为什么判断为高风险？"))

    assert state["question_scope"] == "report_internal"
    assert state["need_tool_query"] is False


@pytest.mark.anyio
async def test_classify_report_related_question_requires_tool_query() -> None:
    state = classify_question_scope_node(_base_state("最近7天这个异常是否持续？"))

    assert state["question_scope"] == "report_related"
    assert state["need_tool_query"] is True


@pytest.mark.parametrize(
    ("question", "expected_scope"),
    [
        ("如果不调用大模型，当前规则能得出哪些结论？", "report_internal"),
        ("把当前报告和其他所有历史报告做完整对比", "ioc_global"),
        ("帮我写一首关于夏天的诗", "out_of_scope"),
    ],
)
def test_classify_regression_cases(question: str, expected_scope: str) -> None:
    state = classify_question_scope_node(_base_state(question))
    assert state["question_scope"] == expected_scope


@pytest.mark.anyio
async def test_boundary_response_does_not_answer_unrelated_question() -> None:
    state = _base_state("帮我写首诗")
    state["question_scope"] = "out_of_scope"

    result = boundary_response_node(state)

    assert result["answer_type"] == "boundary"
    assert "当前报告无关" in result["final_answer"]
    assert "追问本次风险原因" in result["final_answer"]


def test_persist_chat_message_saves_user_and_assistant_messages(
    report_chat_db: Session,
) -> None:
    state = _base_state("这个风险为什么排第一？")
    state["final_answer"] = "根据当前报告，风险排序依据为..."
    state["evidence_refs"] = ["EV_001"]
    state["used_rag"] = True
    state["rag_source_refs"] = ["DOC_001_CHUNK_003"]

    persist_chat_message_node(state)

    session = report_chat_repo.get_session(report_chat_db, "session_test_report_chat")
    messages = report_chat_repo.list_messages(report_chat_db, "session_test_report_chat")
    assert session is not None
    assert session.report_id == 1
    assert session.conversation_id is not None
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].runtime_session_id == messages[1].runtime_session_id
    assert messages[1].evidence_refs == ["EV_001"]
    assert messages[1].query_scope["used_rag"] is True
    assert messages[1].query_scope["rag_source_refs"] == ["DOC_001_CHUNK_003"]
    assert messages[1].trace_id == "trace_test_report_chat"
    conversation = report_chat_db.get(AiConversation, session.conversation_id)
    runtime_session = report_chat_db.get(AiSession, messages[0].runtime_session_id)
    assert conversation is not None
    assert conversation.biz_type == "report_chat"
    assert runtime_session is not None
    assert runtime_session.status == "success"
    assert runtime_session.output_text == "根据当前报告，风险排序依据为..."


@pytest.mark.anyio
async def test_send_chat_message_records_failed_runtime_session(
    report_chat_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_session = report_chat_repo.create_session(
        report_chat_db,
        report_id=1,
        user_id="tester",
    )

    class FailingGraph:
        @staticmethod
        async def ainvoke(_state, **_kwargs):
            raise RuntimeError("模型连接失败")

    monkeypatch.setattr("app.report_chat_agent.service.report_chat_graph", FailingGraph())

    with pytest.raises(RuntimeError, match="模型连接失败"):
        await send_chat_message(
            session_id=report_session.id,
            report_id=1,
            question="为什么是高风险？",
            user_id="tester",
            trace_id="trace_failed_report_chat",
        )

    messages = report_chat_repo.list_messages(report_chat_db, report_session.id)
    assert [message.role for message in messages] == ["user"]
    runtime_session = report_chat_db.get(AiSession, messages[0].runtime_session_id)
    assert runtime_session is not None
    assert runtime_session.status == "failed"
    assert runtime_session.input_text == "为什么是高风险？"
    assert runtime_session.error_message == "模型连接失败"


def test_create_session_reuses_recent_report_user_session(report_chat_db: Session) -> None:
    first = report_chat_repo.get_or_create_session(
        report_chat_db,
        report_id=1,
        user_id="tester",
        title="本质安全报告追问",
    )
    second = report_chat_repo.get_or_create_session(
        report_chat_db,
        report_id=1,
        user_id="tester",
        title="本质安全报告追问",
    )

    assert second.id == first.id


@pytest.mark.anyio
async def test_send_chat_masks_pii_before_persistence_and_graph(
    report_chat_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_session = report_chat_repo.create_session(report_chat_db, report_id=1, user_id="tester")
    captured: dict = {}

    class CapturingGraph:
        @staticmethod
        async def ainvoke(state, **_kwargs):
            captured.update(state)
            return {**state, "message_id": "mock-message"}

    monkeypatch.setattr("app.report_chat_agent.service.report_chat_graph", CapturingGraph())
    raw_mobile = "13812345678"
    await send_chat_message(
        session_id=report_session.id,
        report_id=1,
        question=f"手机号{raw_mobile}，请结合报告说明",
        user_id="tester",
    )

    messages = report_chat_repo.list_messages(report_chat_db, report_session.id)
    assert raw_mobile not in captured["user_question"]
    assert raw_mobile not in messages[0].content
    runtime_session = report_chat_db.get(AiSession, messages[0].runtime_session_id)
    assert runtime_session is not None
    assert raw_mobile not in runtime_session.input_text


@pytest.mark.anyio
async def test_send_chat_blocks_credential_before_graph_and_persists_only_redacted_text(
    report_chat_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_session = report_chat_repo.create_session(report_chat_db, report_id=1, user_id="tester")

    class UnexpectedGraph:
        @staticmethod
        async def ainvoke(_state):
            raise AssertionError("credential input must not reach graph")

    monkeypatch.setattr("app.report_chat_agent.service.report_chat_graph", UnexpectedGraph())
    secret = "sk-test-1234567890"
    result = await send_chat_message(
        session_id=report_session.id,
        report_id=1,
        question=f"RAG接口密钥是{secret}，请验证",
        user_id="tester",
    )

    messages = report_chat_repo.list_messages(report_chat_db, report_session.id)
    assert result["answer_type"] == "boundary"
    assert all(secret not in message.content for message in messages)


@pytest.mark.anyio
@pytest.mark.anyio
async def test_generate_answer_stops_when_report_context_failed_to_load() -> None:
    state = _base_state("为什么判断为高风险？")
    state["errors"] = [{"node": "load_report_context", "message": "报告不存在"}]
    state["report_context"] = {}
    state["retrieved_context"] = [{"type": "report_summary", "content": "无可用报告上下文"}]

    result = await generate_report_answer_node(state)

    assert result["answer_type"] == "insufficient_evidence"
    assert "无法加载" in result["final_answer"]
