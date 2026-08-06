from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.operation_inbox.models import OperationMessage
from app.operation_inbox.repository import OperationMessageRepository
from app.operation_inbox.service import OperationMessageService


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)


def test_enqueue_is_idempotent_for_runtime_session(db: Session) -> None:
    repository = OperationMessageRepository()

    original = repository.enqueue(db, runtime_session_id="sess_001", report_id=7, priority=3)
    duplicate = repository.enqueue(db, runtime_session_id="sess_001", report_id=99, priority=9)

    assert duplicate.id == original.id
    assert duplicate.report_id == 7
    assert db.query(type(original)).count() == 1


def test_enqueue_returns_concurrent_insert_winner_after_integrity_error() -> None:
    repository = OperationMessageRepository()
    winner = OperationMessage(id="msg_winner", runtime_session_id="sess_race")
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [None, winner]
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate runtime session"))

    message = repository.enqueue(db, runtime_session_id="sess_race")

    assert message is winner
    db.rollback.assert_called_once()
    assert db.scalar.call_count == 2


def test_list_filters_and_orders_by_priority_then_creation_time(db: Session) -> None:
    repository = OperationMessageRepository()
    first = repository.enqueue(db, runtime_session_id="sess_001", report_id=1, priority=3)
    second = repository.enqueue(db, runtime_session_id="sess_002", report_id=1, priority=9)
    third = repository.enqueue(db, runtime_session_id="sess_003", report_id=2, priority=9, status="failed")
    first.assignee_id = "operator_1"
    db.commit()

    results = repository.list(db, status="awaiting_review", report_id=1)
    assigned = repository.list(db, assignee_id="operator_1")
    priority_filtered = repository.list(db, priority=9)

    assert [message.id for message in results] == [second.id, first.id]
    assert [message.id for message in assigned] == [first.id]
    assert [message.id for message in priority_filtered] == [second.id, third.id]
    assert third.id not in [message.id for message in results]


def test_count_by_status_groups_rows_and_service_returns_read_models(db: Session) -> None:
    repository = OperationMessageRepository()
    service = OperationMessageService(repository)
    repository.enqueue(db, runtime_session_id="sess_001", status="awaiting_review")
    repository.enqueue(db, runtime_session_id="sess_002", status="awaiting_review")
    repository.enqueue(db, runtime_session_id="sess_003", status="reopened")
    repository.enqueue(db, runtime_session_id="sess_004", status="claimed")
    repository.enqueue(db, runtime_session_id="sess_005", status="resolved")
    repository.enqueue(db, runtime_session_id="sess_006", status="failed")

    summary = service.summary(db)
    messages = service.list_messages(db, status="awaiting_review")

    assert summary == {
        "awaiting_review": 2,
        "reopened": 1,
        "claimed": 1,
        "resolved": 1,
        "failed": 1,
    }
    assert [message["runtime_session_id"] for message in messages] == ["sess_001", "sess_002"]


def test_service_enqueue_returns_a_serialized_message(db: Session) -> None:
    service = OperationMessageService()

    message = service.enqueue(db, runtime_session_id="sess_service_001", priority=4)

    assert message["runtime_session_id"] == "sess_service_001"
    assert message["priority"] == 4


def test_reopen_and_retry_require_an_operator_identity(db: Session) -> None:
    repository = OperationMessageRepository()
    failed = repository.enqueue(db, runtime_session_id="sess_failed", status="failed")
    resolved = repository.enqueue(db, runtime_session_id="sess_resolved", status="resolved")

    assert repository.retry(db, failed.id, "") is None
    assert repository.reopen(db, resolved.id, "") is None
    assert db.get(OperationMessage, failed.id).status == "failed"
    assert db.get(OperationMessage, resolved.id).status == "resolved"
