from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_adapter.tools import execute_analysis_tool, execute_query_tool

MCP_SERVER_NAME = "AIOperationsCenter MCP Server"

mcp = FastMCP(
    name=MCP_SERVER_NAME,
    instructions=(
        "提供智能运营中心（IOC）的数据查询与聚合分析能力，"
        "包括 KPI 指标、告警、隐患风险、工单查询以及综合聚合分析。"
    ),
)


@mcp.tool(
    name="ioc_query_kpi",
    description="查询 IOC 指标数据，例如能耗、碳排放、设备可用率、告警处理率、工单完成率等。",
)
def query_kpi(filters: dict[str, Any] | None = None) -> str:
    return execute_query_tool("kpi_query", filters)


@mcp.tool(
    name="ioc_query_alarms",
    description="查询 IOC 告警数据，例如高能耗异常、设备离线、压力异常、温度异常、安全告警等。",
)
def query_alarms(filters: dict[str, Any] | None = None) -> str:
    return execute_query_tool("alarm_query", filters)


@mcp.tool(
    name="ioc_query_risks",
    description="查询 IOC 隐患风险数据，例如高风险隐患、巡检逾期、能耗异常趋势、安全生产隐患等。",
)
def query_risks(filters: dict[str, Any] | None = None) -> str:
    return execute_query_tool("risk_query", filters)


@mcp.tool(
    name="ioc_query_work_orders",
    description="查询 IOC 工单数据，例如处理中工单、已完成工单、与告警或隐患关联的工单等。",
)
def query_work_orders(filters: dict[str, Any] | None = None) -> str:
    return execute_query_tool("work_order_query", filters)


@mcp.tool(
    name="ioc_analyze_summary",
    description="对 IOC 查询结果做结构化聚合分析（KPI 状态统计、告警等级分组、风险评分），不调用 LLM。",
)
def analyze_summary(
    kpi_data: dict[str, Any] | None = None,
    alarm_data: dict[str, Any] | None = None,
    risk_data: dict[str, Any] | None = None,
    work_order_data: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
) -> str:
    return execute_analysis_tool(kpi_data, alarm_data, risk_data, work_order_data, filters)
