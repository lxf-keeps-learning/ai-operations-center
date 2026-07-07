"""Tool Center 全链路集成测试。

模拟 Graph Node 调用顺序：
  registry → Query Tool → ToolResult → Analysis Tool → Action Tool
"""

import pytest

from app.integrations.ioc.schema import IocApiResponse
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.core.exceptions import ToolNotFoundError
from app.tool_center.core.schemas import BaseToolInput, ToolContext
from app.tool_center.registry import registry
from app.tools.analysis.ioc_summary_tool import AnalysisInput
from app.tools.query.kpi_tool import KpiQueryTool
from app.tools.register import register_all_tools

REQUIRED_TOOLS = {
    "kpi_query",
    "alarm_query",
    "risk_query",
    "work_order_query",
    "ioc_summary_analysis",
    "work_order_draft",
}


class TestToolCenterIntegration:
    def setup_method(self):
        register_all_tools()

    def _run_tool(self, name: str, filters: dict | None = None):
        return registry.get(name).run(BaseToolInput(filters=filters or {}))

    # Step 1: registry 获取 Tool

    def test_registry_returns_all_tools(self):
        assert REQUIRED_TOOLS.issubset(set(registry.list_tools()))

    # Step 2: 调用 Query Tool

    def test_query_kpi_returns_tool_result(self):
        result = self._run_tool("kpi_query", {"department": "能源运营部"})
        assert result.success is True
        assert result.data["total"] > 0
        assert len(result.evidence) > 0
        assert result.trace_id is not None
        assert result.metadata["source"] == "mock_ioc_api"

    def test_query_alarm_returns_tool_result(self):
        result = self._run_tool("alarm_query", {"alarm_level": "high"})
        assert result.success is True
        assert result.data["total"] > 0

    def test_query_risk_returns_tool_result(self):
        result = self._run_tool("risk_query", {"risk_level": "high"})
        assert result.success is True
        assert result.data["total"] > 0

    def test_query_work_order_returns_tool_result(self):
        result = self._run_tool("work_order_query", {"status": "pending"})
        assert result.success is True
        assert result.data["total"] > 0

    # Step 3: 拿到 ToolResult 放入 Analysis Tool

    def test_analysis_accepts_query_results(self):
        kpi = self._run_tool("kpi_query").data
        alarm = self._run_tool("alarm_query").data
        risk = self._run_tool("risk_query").data
        wo = self._run_tool("work_order_query").data

        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = registry.get("ioc_summary_analysis").run(inp)

        assert result.success is True
        assert result.data["risk_score"] >= 0
        assert result.data["risk_level"] in ("low", "medium", "high")
        assert len(result.evidence) > 0
        assert result.trace_id is not None
        assert result.metadata["source"] == "analysis_engine"

    # Step 4: Action Tool 生成工单草稿

    def test_action_draft_from_alarm(self):
        result = registry.get("work_order_draft").run(
            BaseToolInput(
                filters={
                    "source_type": "alarm",
                    "source_id": "alarm_001",
                    "title": "处理冷站出水温度异常",
                    "description": "自动生成",
                    "priority": "high",
                }
            )
        )
        assert result.success is True
        assert result.data["requires_human_confirmation"] is True
        assert result.data["status"] == "draft"
        assert result.data["draft"]["source_title"] == "冷站出水温度异常"
        assert result.metadata["requires_human_confirmation"] is True

    # Step 5: 完整调用链

    def test_full_chain_query_analysis_action(self):
        # 1) 查 KPI
        kpi_r = self._run_tool("kpi_query")
        assert kpi_r.success is True

        # 2) 查告警
        alarm_r = self._run_tool("alarm_query")
        assert alarm_r.success is True

        # 3) 查隐患
        risk_r = self._run_tool("risk_query")
        assert risk_r.success is True

        # 4) 查工单
        work_order_r = self._run_tool("work_order_query")
        assert work_order_r.success is True

        # 5) 聚合分析
        analysis_r = registry.get("ioc_summary_analysis").run(
            AnalysisInput(
                kpi_data=kpi_r.data,
                alarm_data=alarm_r.data,
                risk_data=risk_r.data,
                work_order_data=work_order_r.data,
            )
        )
        assert analysis_r.success is True
        assert analysis_r.data["kpi"]["total"] > 0
        assert analysis_r.data["alarm"]["total"] > 0
        assert analysis_r.data["risk"]["total"] > 0
        assert analysis_r.data["work_order"]["total"] > 0

        # 6) 生成工单草稿（基于 high 告警）
        draft_r = registry.get("work_order_draft").run(
            BaseToolInput(
                filters={
                    "source_type": "alarm",
                    "source_id": "alarm_001",
                    "title": "冷站出水温度异常处理",
                    "description": (
                        f"风险评分 {analysis_r.data['risk_score']}，"
                        f"等级 {analysis_r.data['risk_level']}"
                    ),
                    "priority": "high",
                }
            )
        )
        assert draft_r.success is True
        assert draft_r.data["requires_human_confirmation"] is True

    # Step 6: 错误链路

    def test_nonexistent_tool_returns_error(self):
        with pytest.raises(ToolNotFoundError, match="Tool not found: nonexistent_tool"):
            registry.get("nonexistent_tool")

    def test_query_failure_propagates_as_success_false(self):
        class FailingClient(MockIocApiClient):
            def get_kpis(self, filters: dict | None = None) -> IocApiResponse:
                return IocApiResponse(success=False, error="mock failure")

        tool = KpiQueryTool(client=FailingClient())
        result = tool.run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
