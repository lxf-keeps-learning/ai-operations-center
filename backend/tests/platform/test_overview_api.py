from collections.abc import Iterator
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
from app.utils.timezone import now_local


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        with session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with session_local() as db:
        timestamp = now_local()
        db.add(AiSession(
            id="overview_api_session",
            conversation_id="overview_api_conversation",
            user_id="operator",
            input_text="Show the overview",
            status="running",
            created_at=timestamp,
            updated_at=timestamp,
        ))
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def test_platform_overview_api_returns_the_standard_response_envelope(client: TestClient) -> None:
    """Changing the route or removing the ApiResponse wrapper must fail this contract test."""
    response = client.get("/api/v1/platform/overview")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "traceId": response.json()["traceId"],
        "success": True,
        "data": {
            "metrics": {
                "today_requests": 1,
                "running_tasks": 1,
                "pending_messages": 0,
                "failed_tasks": 0,
                "total_tokens": 0,
                "agent_success_rate": 0.0,
                "average_response_ms": 0.0,
            },
            "recent_sessions": [{
                "id": "overview_api_session",
                "conversation_id": "overview_api_conversation",
                "title": "Untitled conversation",
                "agent": "AI Agent",
                "channel": "runtime",
                "runs": 1,
                "total_tokens": 0,
                "status": "running",
                "updated_at": response.json()["data"]["recent_sessions"][0]["updated_at"],
            }],
        },
    }
