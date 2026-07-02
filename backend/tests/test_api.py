import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import cache as cache_route
from app.db.redis import RedisPingError
from app.main import app
from app.models.item import SystemItem


@pytest.mark.anyio
async def test_health_check() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "UP"
        assert response.json()["data"]["redis"] == "DISABLED"


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

    assert payload["code"] == 5003
    assert payload["message"] == "Redis connection failed"
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
        trace_id = response.json()["traceId"]

        stream_response = await client.get(f"/api/v1/agent/stream?traceId={trace_id}")
        assert stream_response.status_code == 200
        assert "event: done" in stream_response.text


def test_items_route_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/api/cache/ping" in paths
    assert "/api/items" in paths
    assert "/api/items/{id}" in paths


def test_system_items_model_metadata() -> None:
    assert SystemItem.__tablename__ == "system_items"
    assert "name" in SystemItem.__table__.columns
