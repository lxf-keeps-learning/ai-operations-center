import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exception.error_code import NOT_FOUND
from app.main import app


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
