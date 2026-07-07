from app.tool_center.registry import registry
from app.tools.register import register_all_tools


class TestToolRegistryIntegration:
    def setup_method(self):
        register_all_tools()

    def test_list_tools_contains_all_query_tools(self):
        names = registry.list_tools()
        assert "kpi_query" in names
        assert "alarm_query" in names
        assert "risk_query" in names
        assert "work_order_query" in names

    def test_get_kpi_query_tool(self):
        tool = registry.get("kpi_query")
        assert tool.name == "kpi_query"

    def test_get_alarm_query_tool(self):
        tool = registry.get("alarm_query")
        assert tool.name == "alarm_query"

    def test_get_risk_query_tool(self):
        tool = registry.get("risk_query")
        assert tool.name == "risk_query"

    def test_get_work_order_query_tool(self):
        tool = registry.get("work_order_query")
        assert tool.name == "work_order_query"

    def test_no_duplicate_names(self):
        names = registry.list_tools()
        assert len(names) == len(set(names))
