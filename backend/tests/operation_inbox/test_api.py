from collections.abc import Iterator
from datetime import timedelta
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["LANGGRAPH_POSTGRES_URL"] = ""
os.environ["MCP_ENABLED"] = "false"

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.operation_inbox.models import OperationMessage
from app.operation_inbox.status import (
    OP_AWAITING_REVIEW,
    OP_CLAIMED,
    OP_FAILED,
    OP_REOPENED,
    OP_RESOLVED,
)
from app.runtime.models import AiSession
from app.utils.timezone import now_local


@pytest.fixture
def api_db() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session_local
    Base.metadata.drop_all(engine)


def _create_message(
    db: Session,
    *,
    message_id: str,
    runtime_session_id: str,
    status: str,
    priority: int = 0,
    report_id: int | None = None,
    assignee_id: str | None = None,
) -> OperationMessage:
    db.add(AiSession(
        id=runtime_session_id,
        conversation_id=f"conv_{runtime_session_id}",
        user_id="requester",
        task_type="report_chat",
        input_text="为什么需要人工复核？",
        context={"trace_id": f"trace_{runtime_session_id}"},
        status="success" if status != OP_FAILED else "failed",
    ))
    message = OperationMessage(
        id=message_id,
        runtime_session_id=runtime_session_id,
        status=status,
        priority=priority,
        report_id=report_id,
        assignee_id=assignee_id,
        created_at=now_local(),
        updated_at=now_local(),
    )
    db.add(message)
    db.commit()
    return message


def test_messages_api_envelopes_filtered_rows_and_summary(
    api_db: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = api_db
    with session_local() as db:
        _create_message(
            db,
            message_id="msg_matching",
            runtime_session_id="runtime_matching",
            status=OP_AWAITING_REVIEW,
            priority=9,
            report_id=12,
        )
        _create_message(
            db,
            message_id="msg_other_priority",
            runtime_session_id="runtime_other_priority",
            status=OP_AWAITING_REVIEW,
            priority=1,
            report_id=12,
        )
        _create_message(
            db,
            message_id="msg_claimed",
            runtime_session_id="runtime_claimed",
            status=OP_CLAIMED,
        )
        _create_message(
            db,
            message_id="msg_resolved",
            runtime_session_id="runtime_resolved",
            status=OP_RESOLVED,
        )
        _create_message(
            db,
            message_id="msg_reopened",
            runtime_session_id="runtime_reopened",
            status=OP_REOPENED,
        )
        _create_message(
            db,
            message_id="msg_failed",
            runtime_session_id="runtime_failed",
            status=OP_FAILED,
        )
        _create_message(
            db,
            message_id="msg_processing",
            runtime_session_id="runtime_processing",
            status="processing",
        )

    response = client.get(
        "/api/v1/operation/messages",
        params={"status": OP_AWAITING_REVIEW, "priority": 9, "report_id": 12},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["success"] is True
    assert [item["id"] for item in payload["data"]] == ["msg_matching"]
    assert payload["data"][0]["trace_id"] == "trace_runtime_matching"

    summary = client.get("/api/v1/operation/messages/summary").json()
    assert summary["success"] is True
    assert summary["data"] == {
        OP_AWAITING_REVIEW: 2,
        OP_CLAIMED: 1,
        OP_RESOLVED: 1,
        OP_REOPENED: 1,
        OP_FAILED: 1,
        "processing": 1,
        "mine": 0,
    }


def test_message_actions_reject_conflicts_and_allow_valid_lifecycle(
    api_db: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = api_db
    with session_local() as db:
        _create_message(
            db,
            message_id="msg_lifecycle",
            runtime_session_id="runtime_lifecycle",
            status=OP_AWAITING_REVIEW,
        )
        _create_message(
            db,
            message_id="msg_retry",
            runtime_session_id="runtime_retry",
            status=OP_FAILED,
        )

    claimed = client.post(
        "/api/v1/operation/messages/msg_lifecycle/claim",
        json={"operator_id": "operator_a"},
    ).json()
    conflict = client.post(
        "/api/v1/operation/messages/msg_lifecycle/claim",
        json={"operator_id": "operator_b"},
    ).json()
    invalid_release = client.post(
        "/api/v1/operation/messages/msg_lifecycle/release",
        json={"operator_id": "operator_b"},
    ).json()
    resolved = client.post(
        "/api/v1/operation/messages/msg_lifecycle/resolve",
        json={"operator_id": "operator_a", "note": "已核实"},
    ).json()
    reopened = client.post(
        "/api/v1/operation/messages/msg_lifecycle/reopen",
        json={"operator_id": "operator_a"},
    ).json()
    retried = client.post(
        "/api/v1/operation/messages/msg_retry/retry",
        json={"operator_id": "operator_a"},
    ).json()

    assert claimed["success"] is True
    assert claimed["data"]["status"] == OP_CLAIMED
    assert conflict["success"] is False
    assert invalid_release["success"] is False
    assert resolved["data"]["status"] == OP_RESOLVED
    assert reopened["data"]["status"] == OP_REOPENED
    assert retried["data"]["status"] == OP_AWAITING_REVIEW
    assert retried["data"]["retry_count"] == 1


def test_expired_claim_can_be_reclaimed_by_another_operator_through_api(
    api_db: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = api_db
    with session_local() as db:
        message = _create_message(
            db,
            message_id="msg_expired_api",
            runtime_session_id="runtime_expired_api",
            status=OP_CLAIMED,
            assignee_id="operator_a",
        )
        message.claimed_at = now_local() - timedelta(minutes=31)
        message.lease_expires_at = now_local() - timedelta(minutes=1)
        db.commit()

    response = client.post(
        "/api/v1/operation/messages/msg_expired_api/claim",
        json={"operator_id": "operator_b"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["status"] == OP_CLAIMED
    assert response.json()["data"]["assignee_id"] == "operator_b"


def test_message_summary_returns_unpaginated_mine_count_without_changing_global_counts(
    api_db: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """Removing the assignee/status count must make a second operator's claim leak into mine."""
    client, session_local = api_db
    with session_local() as db:
        _create_message(
            db,
            message_id="msg_mine",
            runtime_session_id="runtime_mine",
            status=OP_CLAIMED,
            assignee_id="operator_a",
        )
        _create_message(
            db,
            message_id="msg_other_operator",
            runtime_session_id="runtime_other_operator",
            status=OP_CLAIMED,
            assignee_id="operator_b",
        )
        _create_message(
            db,
            message_id="msg_resolved_by_mine",
            runtime_session_id="runtime_resolved_by_mine",
            status=OP_RESOLVED,
            assignee_id="operator_a",
        )

    payload = client.get("/api/v1/operation/messages/summary", params={"assignee_id": "operator_a"}).json()["data"]

    assert payload[OP_CLAIMED] == 2
    assert payload["mine"] == 1


def test_operation_analysis_message_detail_and_claim_work_without_ai_session(
    api_db: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_local = api_db
    with session_local() as db:
        db.add(OperationMessage(
            id="msg_analysis_trace",
            runtime_session_id="trace_operation_analysis",
            report_id=77,
            status=OP_AWAITING_REVIEW,
            priority=5,
        ))
        db.commit()

    detail = client.get("/api/v1/operation/messages/msg_analysis_trace")
    claimed = client.post(
        "/api/v1/operation/messages/msg_analysis_trace/claim",
        json={"operator_id": "operator_a"},
    )

    detail_payload = detail.json()
    claimed_payload = claimed.json()
    assert detail.status_code == 200
    assert detail_payload["data"]["report_id"] == 77
    assert detail_payload["data"]["trace_id"] == "trace_operation_analysis"
    assert detail_payload["data"]["ai_status"] is None
    assert detail_payload["data"]["conversation_id"] is None
    assert claimed.status_code == 200
    assert claimed_payload["data"]["status"] == OP_CLAIMED
