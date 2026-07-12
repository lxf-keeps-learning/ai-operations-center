import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.skills.contracts import SkillExecutionResult


@pytest.mark.anyio
async def test_list_skills_returns_discoverable_definitions() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills")

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert [item["id"] for item in payload["data"]] == [
        "operation_analysis",
        "report_deep_answer",
    ]
    assert payload["data"][0]["side_effects"]["business_write"] is False


@pytest.mark.anyio
async def test_get_skill_returns_definition() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/operation_analysis")

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["executor_id"] == "operation_analysis_graph"
    assert "kpi_query" in payload["data"]["allowed_tools"]


@pytest.mark.anyio
async def test_get_missing_skill_returns_unified_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/skills/missing_skill")

    payload = response.json()
    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["code"] == 404001


@pytest.mark.anyio
async def test_execute_skill_uses_unified_endpoint(monkeypatch) -> None:
    def fake_execute(definition, inputs, context):
        assert inputs == {"domain": "safety"}
        return SkillExecutionResult(
            skill_id=definition.id,
            skill_version=definition.version,
            trace_id=context.trace_id or "trace_fallback",
            status="success",
            data={"summary": "执行成功"},
        )

    monkeypatch.setattr("app.skills.api.execute_skill", fake_execute)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/skills/operation_analysis/execute",
            json={"inputs": {"domain": "safety"}},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["skill_id"] == "operation_analysis"
    assert payload["data"]["data"]["summary"] == "执行成功"
