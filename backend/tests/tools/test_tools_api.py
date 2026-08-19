import pytest
from httpx import ASGITransport, AsyncClient

from app.core.context.context_holder import clear_all, set_user_context
from app.core.context.user_context import UserContext
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import DB_CONNECTION_ERROR, FORBIDDEN, NOT_FOUND, RATE_LIMIT
from app.main import app
from app.tool_center.contracts import ToolContext, ToolError, ToolResult
from app.tools import api as tools_api_module
from app.tools.api import ToolCallRequest, call_tool


@pytest.mark.anyio
async def test_tools_list_endpoint_returns_registered_tools() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tools")

    payload = response.json()
    names = {item["name"] for item in payload["data"]}

    assert response.status_code == 200
    assert payload["success"] is True
    assert {
        "alarm_query",
        "ioc_summary_analysis",
        "kpi_query",
        "risk_query",
        "work_order_draft",
        "work_order_query",
    }.issubset(names)


@pytest.mark.anyio
async def test_tools_call_endpoint_runs_query_tool() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tools/call",
            json={
                "tool_name": "alarm_query",
                "filters": {"alarm_level": "critical"},
            },
        )

    result = response.json()["data"]

    assert response.status_code == 200
    assert result["success"] is True
    assert result["data"]["total"] == 2
    assert result["metadata"]["source"] == "mock_ioc_api"


@pytest.mark.anyio
async def test_tools_call_endpoint_runs_action_tool_with_params() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tools/call",
            json={
                "tool_name": "work_order_draft",
                "params": {
                    "source_type": "alarm",
                    "source_id": "alarm_001",
                    "title": "处理冷站出水温度异常",
                    "description": "基于告警 alarm_001 生成工单草稿",
                    "priority": "high",
                },
            },
        )

    result = response.json()["data"]

    assert response.status_code == 200
    assert result["success"] is True
    assert result["data"]["requires_human_confirmation"] is True
    assert result["data"]["draft"]["source_title"] == "冷站出水温度异常"
    assert result["metadata"]["requires_human_confirmation"] is True


@pytest.mark.anyio
async def test_tools_call_endpoint_runs_analysis_tool_with_params() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tools/call",
            json={
                "tool_name": "ioc_summary_analysis",
                "params": {
                    "kpi_data": {"items": [{"status": "warning"}]},
                    "alarm_data": {"items": [{"alarm_level": "critical"}]},
                    "risk_data": {"items": [{"risk_level": "medium"}]},
                    "work_order_data": {"items": [{"status": "pending"}]},
                },
            },
        )

    result = response.json()["data"]

    assert response.status_code == 200
    assert result["success"] is True
    assert result["data"]["risk_score"] == 10
    assert result["data"]["risk_level"] == "medium"
    assert result["metadata"]["source"] == "analysis_engine"


@pytest.mark.anyio
async def test_tools_call_endpoint_returns_404_for_missing_tool() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tools/call",
            json={"tool_name": "missing_tool"},
        )

    payload = response.json()

    assert response.status_code == 404
    assert payload["code"] == NOT_FOUND.code
    assert payload["success"] is False


def _identity_test_cleanup() -> None:
    clear_all()


def test_call_tool_derives_identity_from_user_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[ToolContext] = []

    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        captured.append(context)
        return ToolResult(success=True, data={"total": 1})

    set_user_context(
        UserContext(
            user_id="u9",
            username="nine",
            org_id="org9",
            roles=["operator", "viewer"],
        )
    )
    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)
    try:
        call_tool(
            ToolCallRequest(
                tool_name="kpi_query",
                filters={},
                # 请求体中的身份字段必须被忽略
                context=ToolContext(
                    user_id="spoofed",
                    tenant_id="spoofed-org",
                    role="admin",
                    locale="en-US",
                ),
            )
        )
    finally:
        _identity_test_cleanup()

    assert captured[0].user_id == "u9"
    assert captured[0].tenant_id == "org9"
    assert captured[0].role == "operator"
    assert captured[0].caller_type == "external"
    assert captured[0].locale == "en-US"


def test_call_tool_returns_confirmation_challenge_in_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        return ToolResult(
            success=False,
            data=None,
            error=ToolError(code="TOOL_CONFIRMATION_REQUIRED", message="confirm"),
            metadata={"confirmation_token": "token-abc"},
        )

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    response = call_tool(ToolCallRequest(tool_name="work_order_draft"))

    assert response.code == 0
    assert response.data["success"] is False
    assert response.data["metadata"]["confirmation_token"] == "token-abc"


def test_call_tool_maps_forbidden_to_403(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        return ToolResult(
            success=False,
            error=ToolError(code="TOOL_FORBIDDEN", message="denied"),
        )

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    with pytest.raises(AppException) as excinfo:
        call_tool(ToolCallRequest(tool_name="kpi_query"))

    assert excinfo.value.http_status == 403
    assert excinfo.value.code == FORBIDDEN.code


def test_call_tool_maps_rate_limited_to_429(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        return ToolResult(
            success=False,
            error=ToolError(
                code="TOOL_RATE_LIMITED",
                message="too many",
                detail={"retry_after_seconds": 12},
            ),
        )

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    with pytest.raises(AppException) as excinfo:
        call_tool(ToolCallRequest(tool_name="kpi_query"))

    assert excinfo.value.http_status == 429
    assert excinfo.value.code == RATE_LIMIT.code
    assert "12" in excinfo.value.message


def test_call_tool_maps_capability_unavailable_to_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        return ToolResult(
            success=False,
            error=ToolError(code="TOOL_CAPABILITY_UNAVAILABLE", message="missing"),
        )

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    with pytest.raises(AppException) as excinfo:
        call_tool(ToolCallRequest(tool_name="missing_tool"))

    assert excinfo.value.http_status == 404
    assert excinfo.value.code == NOT_FOUND.code


def test_call_tool_maps_registry_unavailable_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        return ToolResult(
            success=False,
            error=ToolError(code="TOOL_REGISTRY_UNAVAILABLE", message="db down"),
        )

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    with pytest.raises(AppException) as excinfo:
        call_tool(ToolCallRequest(tool_name="kpi_query"))

    assert excinfo.value.http_status == 503
    assert excinfo.value.code == DB_CONNECTION_ERROR.code


def test_call_tool_keeps_confirmation_token_and_stable_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def fake_execute(name_or_capability, arguments, context, confirmation_token=None, stable_only=False):
        captured.append({"token": confirmation_token, "stable_only": stable_only})
        return ToolResult(success=True, data={})

    monkeypatch.setattr(tools_api_module, "execute_tool", fake_execute)

    call_tool(
        ToolCallRequest(
            tool_name="work_order_draft",
            confirmation_token="tok-1",
            stable_only=True,
        )
    )

    assert captured == [{"token": "tok-1", "stable_only": True}]
