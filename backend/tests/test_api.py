from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import cache as cache_route
from app.core.config.llm_settings import llm_settings
from app.core.exception.error_code import REDIS_CONNECTION_ERROR, VALIDATION_ERROR
from app.db.base import Base
from app.db.redis import RedisPingError
from app.main import app
from app.models.item import SystemItem
from app.runtime.llm.client import LlmResult, _default_runtime_prompt
from app.runtime.models import (
    AiConversation,
    AiFeedback,
    AiPrompt,
    AiSession,
    AiTrace,
)
from app.runtime.repositories.prompt_repository import PromptRepository
from app.runtime.runtime_service import runtime_service
from app.runtime.schemas.prompt_schema import PromptCreate
from app.runtime.services.session_service import session_service
from app.runtime.services.trace_service import trace_service

_RUNTIME_MODELS = (AiConversation, AiFeedback, AiPrompt, AiSession, AiTrace)


@pytest.fixture
def runtime_db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with session_local() as db:
        yield db

    Base.metadata.drop_all(engine)


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


def _fake_llm_result(content: str, system_prompt: str = "测试系统 Prompt") -> LlmResult:
    return LlmResult(
        content=content,
        model="deepseek-chat",
        prompt_tokens=8,
        completion_tokens=6,
        total_tokens=14,
        cost_ms=12,
        success=True,
        system_prompt=system_prompt,
    )


def test_default_runtime_prompt_identifies_deepseek_not_openai() -> None:
    provider = llm_settings.get_provider("deepseek")
    assert provider is not None

    prompt = _default_runtime_prompt(provider)

    assert "DeepSeek" in prompt
    assert provider.model in prompt
    assert "不要自称 OpenAI" in prompt
    assert "GPT" in prompt
    assert "已接入 LangGraph" in prompt
    assert "START → init_session → load_prompt → call_llm → finalize → END" in prompt


def test_runtime_chat_records_prompt_version_and_span_chain(
    runtime_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_content = (
        "请面向智能运营中心，"
        "结合上下文给出可追溯的告警分析。"
    )
    prompt = PromptRepository().create(
        runtime_db_session,
        PromptCreate(
            code="ioc_alarm_analysis",
            name="运营告警分析",
            content=prompt_content,
            scene_code="alarm",
            created_by="tester",
        ),
    )
    PromptRepository().update_status(runtime_db_session, prompt.id, "active")

    def fake_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> LlmResult:
        assert prompt_content == prompt.content
        assert user_message == "分析今日高风险告警"
        assert history == []
        return _fake_llm_result(
            "这是 DeepSeek 生成的告警分析。",
            system_prompt=prompt.content,
        )

    monkeypatch.setattr("app.runtime.nodes.call_llm_node.llm_client.chat", fake_chat)

    result = runtime_service.chat(
        db=runtime_db_session,
        user_id="u_sprint2",
        message="分析今日高风险告警",
        biz_type="alarm",
        prompt_code="ioc_alarm_analysis",
    )

    spans = trace_service.list_by_trace_id(runtime_db_session, result["trace_id"])
    span_types = [span.span_type for span in spans]
    assert span_types == ["runtime", "graph", "node", "tool", "llm", "runtime"]

    llm_span = next(span for span in spans if span.span_type == "llm")
    assert llm_span.prompt_id == prompt.id
    assert llm_span.prompt_code == "ioc_alarm_analysis"
    assert llm_span.prompt_version == 1
    assert llm_span.prompt_snapshot == prompt.content
    assert llm_span.model_name == "deepseek-chat"
    assert llm_span.total_tokens is not None
    assert llm_span.total_tokens > 0

    tool_span = next(span for span in spans if span.span_type == "tool")
    assert tool_span.output_data
    assert tool_span.output_data["context_source"] == "mysql_session_json"

    session = session_service.get_by_id(runtime_db_session, result["session_id"])
    assert session is not None
    assert session.status == "success"
    assert session.output_text == result["answer"]
    assert result["reply"] == result["answer"]
    assert trace_service.list_by_session_id(runtime_db_session, result["session_id"]) == spans


def test_runtime_chat_falls_back_to_system_prompt_when_code_missing(
    runtime_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_code = "missing_runtime_prompt"

    def fake_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> LlmResult:
        assert prompt_content is None
        assert user_message == "使用兜底提示词回答"
        assert history == []
        return _fake_llm_result(
            "已使用系统 Prompt 回答。",
            system_prompt="内置 Runtime 系统 Prompt",
        )

    monkeypatch.setattr("app.runtime.nodes.call_llm_node.llm_client.chat", fake_chat)

    result = runtime_service.chat(
        db=runtime_db_session,
        user_id="u_prompt_fallback",
        message="使用兜底提示词回答",
        prompt_code=requested_code,
    )

    session = session_service.get_by_id(runtime_db_session, result["session_id"])
    spans = trace_service.list_by_trace_id(runtime_db_session, result["trace_id"])
    prompt_span = next(span for span in spans if span.node_name == "load_active_prompt")
    llm_span = next(span for span in spans if span.span_type == "llm")

    assert session is not None
    assert session.status == "success"
    assert result["answer"] == "已使用系统 Prompt 回答。"
    assert prompt_span.status == "success"
    assert prompt_span.output_data == {
        "prompt_found": False,
        "fallback_to_system_prompt": True,
        "requested_prompt_code": requested_code,
    }
    assert llm_span.prompt_id is None
    assert llm_span.prompt_code == requested_code
    assert llm_span.prompt_version is None
    assert llm_span.prompt_snapshot == "内置 Runtime 系统 Prompt"
    assert llm_span.input_data["fallback_to_system_prompt"] is True


def test_runtime_chat_passes_conversation_history_to_llm(
    runtime_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> LlmResult:
        calls.append(
            {
                "prompt_content": prompt_content,
                "user_message": user_message,
                "history": history or [],
            }
        )
        return _fake_llm_result(f"回答：{user_message}")

    monkeypatch.setattr("app.runtime.nodes.call_llm_node.llm_client.chat", fake_chat)

    first = runtime_service.chat(
        db=runtime_db_session,
        user_id="u_sprint2",
        message="记住：园区A今天有高风险告警",
    )
    runtime_service.chat(
        db=runtime_db_session,
        user_id="u_sprint2",
        message="我刚才说的是哪个园区？",
        conversation_id=first["conversation_id"],
    )

    assert calls[0]["history"] == []
    assert calls[1]["history"] == [
        {"role": "user", "content": "记住：园区A今天有高风险告警"},
        {"role": "assistant", "content": "回答：记住：园区A今天有高风险告警"},
    ]


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
