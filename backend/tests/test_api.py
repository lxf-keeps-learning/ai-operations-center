import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import cache as cache_route
from app.core.exception.error_code import REDIS_CONNECTION_ERROR, VALIDATION_ERROR
from app.db.redis import RedisPingError
from app.main import app
from app.models.item import SystemItem


@pytest.mark.anyio
async def test_health_check() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

        payload = response.json()
        assert response.status_code == 200
        assert payload["success"] is True
        assert payload["traceId"] == response.headers["X-Trace-Id"]
        assert payload["data"]["status"] == "UP"
        assert payload["data"]["env"] in {"local", "dev", "test", "prod"}
        assert payload["data"]["version"]
        assert payload["data"]["redis"] == "DISABLED"


@pytest.mark.anyio
async def test_trace_header_is_reused_in_body_and_context() -> None:
    trace_id = "trace_test_reuse_001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/context/current",
            headers={
                "X-Trace-Id": trace_id,
                "X-User-Id": "u_001",
                "X-Username": "tester",
                "X-Page-Code": "infra_dashboard",
            },
        )

        payload = response.json()
        assert response.status_code == 200
        assert response.headers["X-Trace-Id"] == trace_id
        assert payload["traceId"] == trace_id
        assert payload["data"]["requestContext"]["traceId"] == trace_id
        assert payload["data"]["requestContext"]["path"] == "/api/v1/context/current"
        assert payload["data"]["userContext"]["userId"] == "u_001"
        assert payload["data"]["pageContext"]["pageCode"] == "infra_dashboard"


@pytest.mark.anyio
async def test_validation_error_uses_unified_response() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/agent/chat", json={})

        payload = response.json()
        assert response.status_code == 422
        assert payload["code"] == VALIDATION_ERROR.code
        assert payload["message"] == VALIDATION_ERROR.message
        assert payload["success"] is False
        assert payload["traceId"] == response.headers["X-Trace-Id"]


@pytest.mark.anyio
async def test_model_config_does_not_expose_api_keys() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/config/models")

        payload = response.json()
        providers = {item["provider"] for item in payload["data"]}
        assert response.status_code == 200
        assert providers == {"qwen", "deepseek", "doubao"}
        assert all("apiKey" not in item and "api_key" not in item for item in payload["data"])


@pytest.mark.anyio
async def test_cache_ping_disabled_by_default() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/cache/ping")

        assert response.status_code == 200
        payload = response.json()
        assert payload["message"] == "Redis disabled"
        assert payload["data"]["enabled"] is False
        assert payload["data"]["status"] == "disabled"


def test_cache_ping_enabled_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_route.settings, "redis_enabled", True)
    monkeypatch.setattr(cache_route.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(cache_route, "ping_redis", lambda redis_url: "pong")

    payload = cache_route.ping_cache().model_dump(by_alias=True)

    assert payload["message"] == "pong"
    assert payload["data"]["enabled"] is True
    assert payload["data"]["status"] == "up"
    assert payload["data"]["response"] == "pong"


def test_cache_ping_enabled_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_ping(redis_url: str) -> str:
        raise RedisPingError("connect refused")

    monkeypatch.setattr(cache_route.settings, "redis_enabled", True)
    monkeypatch.setattr(cache_route.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(cache_route, "ping_redis", fail_ping)

    payload = cache_route.ping_cache().model_dump(by_alias=True)

    assert payload["code"] == REDIS_CONNECTION_ERROR.code
    assert payload["message"] == REDIS_CONNECTION_ERROR.message
    assert payload["success"] is False
    assert payload["data"]["enabled"] is True
    assert payload["data"]["status"] == "error"
    assert payload["data"]["error"] == "connect refused"


@pytest.mark.anyio
async def test_analyze_task_and_stream() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/analyze",
            json={
                "agent_code": "operation",
                "scene_code": "operation_daily_summary",
                "message": "生成今日运营摘要",
                "conversation_id": None,
                "page_context": {"page": "operation_center", "filters": {"date": "2026-07-02"}},
                "business_context": {"object_type": "operation_dashboard", "object_id": "demo"},
                "stream": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        trace_id = payload["traceId"]
        assert trace_id == response.headers["X-Trace-Id"]
        assert payload["data"]["stream_url"].endswith(f"traceId={trace_id}")

        stream_response = await client.get(f"/api/v1/agent/stream?traceId={trace_id}")
        assert stream_response.status_code == 200
        assert "event: done" in stream_response.text


def test_items_route_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/api/cache/ping" in paths
    assert "/api/v1/items" in paths
    assert "/api/v1/items/{id}" in paths


def test_system_items_model_metadata() -> None:
    assert SystemItem.__tablename__ == "system_items"
    assert "name" in SystemItem.__table__.columns
