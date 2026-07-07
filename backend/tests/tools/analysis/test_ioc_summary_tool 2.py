from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.registry import registry
from app.tools.analysis.ioc_summary_tool import AnalysisInput, IocSummaryAnalysisTool
from app.tools.query.alarm_tool import AlarmQueryTool
from app.tools.query.kpi_tool import KpiQueryTool
from app.tools.query.risk_tool import RiskQueryTool
from app.tools.query.work_order_tool import WorkOrderQueryTool
from app.tools.register import register_all_tools


class TestIocSummaryAnalysisTool:
    def setup_method(self):
        self.tool = IocSummaryAnalysisTool()
        self.client = MockIocApiClient()

    def _query_all(self):
        kpi = self.client.get_kpis().data
        alarm = self.client.get_alarms().data
        risk = self.client.get_risks().data
        wo = self.client.get_work_orders().data
        return kpi, alarm, risk, wo

    def test_analysis_returns_success(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.success is True

    def test_analysis_contains_all_sections(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert "kpi" in result.data
        assert "alarm" in result.data
        assert "risk" in result.data
        assert "work_order" in result.data
        assert "risk_score" in result.data
        assert "risk_level" in result.data

    def test_analysis_kpi_stats(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["kpi"]["total"] > 0
        assert "by_status" in result.data["kpi"]

    def test_analysis_alarm_stats(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["alarm"]["total"] > 0
        assert "by_level" in result.data["alarm"]

    def test_analysis_risk_stats(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["risk"]["total"] > 0
        assert "by_level" in result.data["risk"]

    def test_analysis_work_order_stats(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["work_order"]["total"] > 0
        assert "by_status" in result.data["work_order"]

    def test_risk_score_is_non_negative(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["risk_score"] >= 0
        assert result.data["risk_level"] in ("low", "medium", "high")

    def test_empty_data_returns_zero_scores(self):
        inp = AnalysisInput()
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["kpi"]["total"] == 0
        assert result.data["alarm"]["total"] == 0
        assert result.data["risk"]["total"] == 0
        assert result.data["work_order"]["total"] == 0
        assert result.data["risk_score"] == 0
        assert result.data["risk_level"] == "low"

    def test_returns_evidence(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert len(result.evidence) > 0
        assert result.evidence[0].source == "analysis_engine"

    def test_returns_trace_id(self):
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.trace_id is not None

    def test_registered_in_registry(self):
        register_all_tools()
        tool = registry.get("ioc_summary_analysis")
        assert tool.name == "ioc_summary_analysis"

    def test_not_calling_llm(self):
        """Analysis Tool 不调用 LLM，只做确定性聚合"""
        kpi, alarm, risk, wo = self._query_all()
        inp = AnalysisInput(kpi_data=kpi, alarm_data=alarm, risk_data=risk, work_order_data=wo)
        result = self.tool.run(inp)
        assert result.data["risk_score"] == sum(
            (5 if a.get("alarm_level") == "critical" else 3 if a.get("alarm_level") == "high" else 1 if a.get("alarm_level") == "medium" else 0)
            for a in alarm.get("items", [])
        ) + sum(
            (4 if r.get("risk_level") == "high" else 2 if r.get("risk_level") == "medium" else 0)
            for r in risk.get("items", [])
        ) + sum(
            (4 if k.get("status") == "critical" else 2 if k.get("status") == "warning" else 0)
            for k in kpi.get("items", [])
        ) + sum(1 for w in (wo or {}).get("items", []) if w.get("status") == "pending")
