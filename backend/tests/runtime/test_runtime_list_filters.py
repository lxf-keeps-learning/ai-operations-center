from collections.abc import Iterator
from datetime import datetime
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
from app.runtime.models.session_model import AiSession
from app.runtime.models.trace_model import AiTrace


@pytest.fixture
def client_and_session_factory() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session_factory
    Base.metadata.drop_all(engine)


def _add_session(db: Session, session_id: str, created_at: datetime, status: str = "success") -> None:
    db.add(AiSession(
        id=session_id,
        conversation_id=f"conversation-{session_id}",
        user_id="operator",
        input_text="Review the operation result",
        status=status,
        created_at=created_at,
        updated_at=created_at,
    ))


def _add_trace(
    db: Session,
    trace_id: str,
    session_id: str,
    *,
    created_at: datetime = datetime(2026, 8, 6, 12, 0, 0),
    span_type: str = "llm",
) -> None:
    db.add(AiTrace(
        id=trace_id,
        trace_id=trace_id,
        session_id=session_id,
        span_type=span_type,
        status="success",
        created_at=created_at,
    ))


def test_session_list_applies_session_and_inclusive_date_filters(
    client_and_session_factory: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """Dropping a session or date predicate must expose unrelated sessions."""
    client, session_factory = client_and_session_factory
    with session_factory() as db:
        _add_session(db, "session-match", datetime(2026, 8, 6, 9, 0, 0))
        _add_session(db, "session-too-old", datetime(2026, 8, 5, 23, 59, 59))
        _add_session(db, "session-other", datetime(2026, 8, 6, 9, 0, 0))
        db.commit()

    response = client.get(
        "/api/v1/runtime/sessions",
        params={"session_id": "session-match", "date_from": "2026-08-06", "date_to": "2026-08-06"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["session-match"]


def test_trace_list_applies_session_filter(
    client_and_session_factory: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """Dropping the session predicate must expose spans from another session."""
    client, session_factory = client_and_session_factory
    with session_factory() as db:
        _add_trace(db, "trace-match", "session-match")
        _add_trace(db, "trace-other", "session-other")
        db.commit()

    response = client.get("/api/v1/runtime/traces", params={"session_id": "session-match"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["trace-match"]


def test_trace_list_applies_trace_id_filter(
    client_and_session_factory: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """Dropping the trace predicate must expose another trace in the same session."""
    client, session_factory = client_and_session_factory
    with session_factory() as db:
        _add_trace(db, "trace-match", "session-shared")
        _add_trace(db, "trace-other", "session-shared")
        db.commit()

    response = client.get("/api/v1/runtime/traces", params={"trace_id": "trace-match"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["trace-match"]


def test_session_list_accepts_multiple_status_values(
    client_and_session_factory: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_and_session_factory
    with session_factory() as db:
        _add_session(db, "session-queued", datetime(2026, 8, 6, 9, 0, 0), status="queued")
        _add_session(db, "session-running", datetime(2026, 8, 6, 10, 0, 0), status="running")
        _add_session(db, "session-success", datetime(2026, 8, 6, 11, 0, 0), status="success")
        db.commit()

    response = client.get("/api/v1/runtime/sessions", params={"status": "queued,running"})

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {"session-queued", "session-running"}


def test_trace_list_applies_span_type_and_local_date_filters(
    client_and_session_factory: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_and_session_factory
    with session_factory() as db:
        _add_trace(db, "trace-in-range", "session-match", created_at=datetime(2026, 8, 7, 9, 0, 0))
        _add_trace(db, "trace-before-range", "session-match", created_at=datetime(2026, 8, 6, 23, 59, 59))
        _add_trace(db, "trace-non-llm", "session-match", created_at=datetime(2026, 8, 7, 10, 0, 0), span_type="tool")
        db.commit()

    response = client.get(
        "/api/v1/runtime/traces",
        params={"span_type": "llm", "date_from": "2026-08-07", "date_to": "2026-08-07"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["trace-in-range"]
