import pytest
from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.integrations.ioc.schema import IocApiResponse
from app.tool_center.registry import registry
from app.tool_center.contracts import BaseToolInput
from app.tools.query.work_order_tool import WorkOrderQueryTool
from app.tools.register import register_all_tools


class TestWorkOrderQueryTool:
    def setup_method(self):
        self.client = MockIocApiClient()
        self.tool = WorkOrderQueryTool(client=self.client)

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_execute_returns_success(self):
        result = await self.tool.run(BaseToolInput())
        assert result.success is True

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_execute_returns_data_items(self):
        result = await self.tool.run(BaseToolInput())
        assert "items" in result.data
        assert len(result.data["items"]) > 0

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_execute_returns_data_total(self):
        result = await self.tool.run(BaseToolInput())
        assert "total" in result.data
        assert result.data["total"] > 0

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_execute_returns_evidence(self):
        result = await self.tool.run(BaseToolInput())
        assert len(result.evidence) > 0
        assert result.evidence[0].source == "mock_ioc_api"
        assert result.evidence[0].source_type == "work_order_api"

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_execute_returns_trace_id(self):
        result = await self.tool.run(BaseToolInput())
        assert result.trace_id is not None
        assert result.trace_id.startswith("trace_")

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_filter_by_status(self):
        inp = BaseToolInput(filters={"status": "pending"})
        result = await self.tool.run(inp)
        assert result.success is True
        for item in result.data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_filter_by_owner(self):
        inp = BaseToolInput(filters={"owner": "张工"})
        result = await self.tool.run(inp)
        assert result.success is True
        for item in result.data["items"]:
            assert item["owner"] == "张工"

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_filter_by_related_alarm(self):
        inp = BaseToolInput(filters={"related_alarm_id": "alarm_001"})
        result = await self.tool.run(inp)
        assert result.success is True
        for item in result.data["items"]:
            assert item["related_alarm_id"] == "alarm_001"

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_filter_by_department(self):
        inp = BaseToolInput(filters={"department": "能源运营部"})
        result = await self.tool.run(inp)
        assert result.success is True
        assert result.data["total"] > 0
        for item in result.data["items"]:
            assert item["department"] == "能源运营部"

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_filter_no_match_returns_empty(self):
        inp = BaseToolInput(filters={"status": "nonexistent"})
        result = await self.tool.run(inp)
        assert result.success is True
        assert result.data["total"] == 0
        assert result.metadata["empty"] is True

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_ioc_failure_returns_error(self):
        class FailingClient(IocApiClient):
            async def aget_kpis(self, filters=None): return IocApiResponse(success=False)
            async def aget_alarms(self, filters=None): return IocApiResponse(success=False)
            async def aget_risks(self, filters=None): return IocApiResponse(success=False)
            async def aget_work_orders(self, filters=None): return IocApiResponse(success=False, error="API unavailable")

        tool = WorkOrderQueryTool(client=FailingClient())
        result = await tool.run(BaseToolInput())
        assert result.success is False
        assert result.error.code == "WORK_ORDER_QUERY_FAILED"

    @pytest.mark.anyio
    async def test_invalid_filter_returns_error(self):
        result = await self.tool.run(BaseToolInput(filters={"unknown": "value"}))
        assert result.success is False
        assert result.error.code == "WORK_ORDER_QUERY_FAILED"
        assert "Unsupported filters: unknown" in result.error.detail["reason"]

    @pytest.mark.anyio
    async def test_registered_in_registry(self):
        register_all_tools()
        tool = registry.get("work_order_query")
        assert tool.name == "work_order_query"
