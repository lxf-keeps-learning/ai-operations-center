from collections.abc import Iterator
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

os.environ["LANGGRAPH_POSTGRES_URL"] = ""
os.environ["MCP_ENABLED"] = "false"

from app.db.base import Base
from app.operation_agent.services import record_service
from app.operation_agent.services.record_service import save_analysis_result
from app.operation_inbox.models import OperationMessage
from app.operation_inbox.service import enqueue_for_review
from app.operation_inbox.status import OP_AWAITING_REVIEW, OP_FAILED
from app.report_chat_agent.repositories import report_chat_repo


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)


def test_enqueue_for_review_is_idempotent_for_one_runtime_session(db: Session) -> None:
    first = enqueue_for_review(
        db,
        runtime_session_id="runtime_once",
        report_chat_message_id="message_once",
        report_id=31,
    )
    duplicate = enqueue_for_review(
        db,
        runtime_session_id="runtime_once",
        report_chat_message_id="other_message",
        report_id=99,
    )

    assert duplicate.id == first.id
    assert duplicate.report_id == 31
    assert db.scalar(select(OperationMessage).where(OperationMessage.runtime_session_id == "runtime_once")) == first


def test_report_chat_completion_and_failure_produce_review_messages(db: Session) -> None:
    chat_session = report_chat_repo.create_session(db, report_id=7, user_id="operator")
    completed_runtime = report_chat_repo.begin_turn(
        db,
        session=chat_session,
        question="完成后请复核",
        trace_id="trace_completed",
    )
    report_chat_repo.complete_turn(
        db,
        session_id=chat_session.id,
        runtime_session_id=completed_runtime.id,
        report_id=7,
        content="AI 回复",
        trace_id="trace_completed",
        question_scope="report_internal",
        answer_type="normal",
        evidence_refs=[],
        query_scope={},
        used_rag=False,
        rag_source_refs=[],
        rag_sources=[],
    )
    failed_runtime = report_chat_repo.begin_turn(
        db,
        session=chat_session,
        question="失败后请复核",
        trace_id="trace_failed",
    )
    report_chat_repo.fail_turn(
        db,
        runtime_session_id=failed_runtime.id,
        error_message="模型不可用",
    )

    messages = {
        message.runtime_session_id: message
        for message in db.scalars(select(OperationMessage))
    }

    assert messages[completed_runtime.id].status == OP_AWAITING_REVIEW
    assert messages[failed_runtime.id].status == OP_FAILED
    assert messages[completed_runtime.id].report_id == 7
    assert messages[failed_runtime.id].error_message == "模型不可用"


def test_report_chat_service_preserves_answer_when_inbox_enqueue_fails(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.report_chat_agent import service as chat_service

    report_chat = report_chat_repo.create_session(db, report_id=8, user_id="operator")

    class CompletedGraph:
        @staticmethod
        async def ainvoke(state, **_kwargs):
            return {**state, "message_id": "assistant_from_graph", "final_answer": "AI 回复"}

    monkeypatch.setattr(chat_service, "get_session_local", lambda: lambda: db)
    monkeypatch.setattr(chat_service, "report_chat_graph", CompletedGraph())
    monkeypatch.setattr(
        "app.operation_inbox.service.enqueue_for_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("inbox unavailable")),
    )

    import asyncio
    result = asyncio.run(chat_service.send_chat_message(
        session_id=report_chat.id,
        report_id=8,
        question="请复核这条回答",
        user_id="operator",
        trace_id="trace_enqueue_failure",
    ))

    assert result["final_answer"] == "AI 回复"
    assert result["runtime_session_id"]


def test_operation_record_completion_enqueues_using_trace_and_record_identifiers(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_with_explicit_sqlite_id(
        session: Session,
        record,
    ):
        record.id = 77
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    monkeypatch.setattr(
        record_service.analysis_record_repo,
        "create",
        create_with_explicit_sqlite_id,
    )
    record = save_analysis_result(
        db,
        trace_id="trace_operation_record",
        page_context={"domain": "safety", "trigger_type": "manual"},
        input_snapshot={},
        result={"final_answer": "分析完成", "llm_usages": []},
        status="success",
    )

    message = db.scalar(
        select(OperationMessage).where(OperationMessage.runtime_session_id == "trace_operation_record")
    )

    assert message is not None
    assert message.report_id == record.id == 77
    assert message.status == OP_AWAITING_REVIEW


def test_operation_record_result_survives_review_enqueue_failure(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_with_explicit_sqlite_id(session: Session, record):
        record.id = 78
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    monkeypatch.setattr(
        record_service.analysis_record_repo,
        "create",
        create_with_explicit_sqlite_id,
    )
    monkeypatch.setattr(
        "app.operation_inbox.service.enqueue_for_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("inbox unavailable")),
    )

    record = save_analysis_result(
        db,
        trace_id="trace_operation_enqueue_failure",
        page_context={"domain": "safety", "trigger_type": "manual"},
        input_snapshot={},
        result={"final_answer": "分析完成", "llm_usages": []},
        status="success",
    )

    assert record.id == 78
