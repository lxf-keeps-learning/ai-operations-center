from typing import Any

from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_center.registry import get_tool


MCP_TOOL_MAP: dict[str, str] = {
    "ioc_query_kpi": "kpi_query",
    "ioc_query_alarms": "alarm_query",
    "ioc_query_risks": "risk_query",
    "ioc_query_work_orders": "work_order_query",
    "ioc_analyze_summary": "ioc_summary_analysis",
}


def execute_query_tool(registry_name: str, filters: dict[str, Any] | None = None) -> str:
    tool = get_tool(registry_name)
    inp = BaseToolInput(context=ToolContext(), filters=filters or {})
    result = tool.run(inp)
    return result.model_dump_json(indent=2, exclude_none=True)


def execute_analysis_tool(
    kpi_data: dict[str, Any] | None = None,
    alarm_data: dict[str, Any] | None = None,
    risk_data: dict[str, Any] | None = None,
    work_order_data: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
) -> str:
    tool = get_tool("ioc_summary_analysis")
    merged_filters = filters or {}
    if kpi_data is not None:
        merged_filters["kpi_data"] = kpi_data
    if alarm_data is not None:
        merged_filters["alarm_data"] = alarm_data
    if risk_data is not None:
        merged_filters["risk_data"] = risk_data
    if work_order_data is not None:
        merged_filters["work_order_data"] = work_order_data
    inp = BaseToolInput(context=ToolContext(), filters=merged_filters)
    result = tool.run(inp)
    return result.model_dump_json(indent=2, exclude_none=True)
