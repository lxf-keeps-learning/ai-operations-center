from __future__ import annotations

from collections.abc import Iterator
import os

os.environ["MCP_ENABLED"] = "false"
os.environ["LANGGRAPH_POSTGRES_URL"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.tool_registry.models import ToolCallAudit

ADMIN_HEADERS = {"X-Roles": "admin", "X-User-Id": "admin-1", "X-Org-Id": "org-a"}


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
    with TestClient(app) as test_client:
        test_client.session_local = session_local
        yield test_client
    Base.metadata.drop_all(engine)


def test_list_tools_requires_admin(client: TestClient) -> None:
    response = client.get("/api/v1/tool-registry/tools")

    assert response.status_code == 403
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == 403001


def test_list_tools_as_admin_returns_empty(client: TestClient) -> None:
    response = client.get("/api/v1/tool-registry/tools", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == []


def test_create_tool_returns_envelope_and_persists(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tool-registry/tools",
        headers=ADMIN_HEADERS,
        json={
            "tool_key": "kpi_query",
            "capability": "query.kpi",
            "name": "KPI Query",
            "description": "Returns KPI data",
            "tool_type": "query",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["tool_key"] == "kpi_query"
    assert payload["data"]["capability"] == "query.kpi"

    listed = client.get("/api/v1/tool-registry/tools", headers=ADMIN_HEADERS).json()
    assert [tool["tool_key"] for tool in listed["data"]] == ["kpi_query"]


def test_create_tool_without_admin_returns_403(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tool-registry/tools",
        headers={"X-Roles": "operator"},
        json={
            "tool_key": "kpi_query",
            "capability": "query.kpi",
            "name": "KPI Query",
            "description": "Returns KPI data",
            "tool_type": "query",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403001


def test_publish_validates_release_type(client: TestClient) -> None:
    client.post(
        "/api/v1/tool-registry/tools",
        headers=ADMIN_HEADERS,
        json={
            "tool_key": "kpi_query",
            "capability": "query.kpi",
            "name": "KPI Query",
            "description": "Returns KPI data",
            "tool_type": "query",
        },
    )
    client.post(
        "/api/v1/tool-registry/tools/kpi_query/versions",
        headers=ADMIN_HEADERS,
        json={
            "version": "1.0.0",
            "implementation_ref": "builtin.kpi_query",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
        },
    )

    response = client.post(
        "/api/v1/tool-registry/tools/kpi_query/versions/1.0.0/publish",
        headers=ADMIN_HEADERS,
        json={"release_type": "boom"},
    )

    assert response.status_code == 422


def test_publish_rejects_unbound_executor_with_400(client: TestClient) -> None:
    client.post(
        "/api/v1/tool-registry/tools",
        headers=ADMIN_HEADERS,
        json={
            "tool_key": "new_tool",
            "capability": "query.new",
            "name": "New Tool",
            "description": "New",
            "tool_type": "query",
        },
    )
    client.post(
        "/api/v1/tool-registry/tools/new_tool/versions",
        headers=ADMIN_HEADERS,
        json={
            "version": "1.0.0",
            "implementation_ref": "builtin.unbound",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
        },
    )

    response = client.post(
        "/api/v1/tool-registry/tools/new_tool/versions/1.0.0/publish",
        headers=ADMIN_HEADERS,
        json={"release_type": "stable"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "implementation_ref" in payload["message"]


def test_audit_list_filters_and_paginates(client: TestClient) -> None:
    session_local = client.session_local
    with session_local() as session:
        session.add(
            ToolCallAudit(
                trace_id="trace-1",
                tool_id=None,
                version_id=None,
                implementation_ref=None,
                tenant_id="tenant-a",
                user_id="u1",
                role="operator",
                caller_type="internal",
                policy_id=None,
                decision="allowed",
                gray_bucket=None,
                selected_stable=None,
                status="success",
                duration_ms=None,
                error_code=None,
                argument_hash="h1",
                argument_summary={"a": 1},
            )
        )
        session.add(
            ToolCallAudit(
                trace_id="trace-2",
                tool_id=None,
                version_id=None,
                implementation_ref=None,
                tenant_id="tenant-a",
                user_id="u1",
                role="operator",
                caller_type="internal",
                policy_id=None,
                decision="denied",
                gray_bucket=None,
                selected_stable=None,
                status="failed",
                duration_ms=None,
                error_code=None,
                argument_hash="h2",
                argument_summary={"a": 2},
            )
        )
        session.commit()

    response = client.get(
        "/api/v1/tool-registry/audits",
        headers=ADMIN_HEADERS,
        params={"decision": "allowed", "offset": 0, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]["items"]) == 1
    assert payload["data"]["items"][0]["trace_id"] == "trace-1"
    assert payload["data"]["total"] == 1


def test_audit_list_requires_admin(client: TestClient) -> None:
    response = client.get("/api/v1/tool-registry/audits")

    assert response.status_code == 403
    assert response.json()["code"] == 403001
