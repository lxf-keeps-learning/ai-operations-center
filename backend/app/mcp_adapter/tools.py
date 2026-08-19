from typing import Any

from app.tool_center.contracts import ToolContext
from app.tool_registry.compat import execute_tool

# 稳定公共 MCP 工具名 -> capability 的兼容映射。
# 公共名称保持不变，具体版本与治理由 Registry/Gateway 决定。
MCP_TOOL_MAP: dict[str, str] = {
    "ioc_query_kpi": "query.kpi",
    "ioc_query_alarms": "query.alarm",
    "ioc_query_risks": "query.risk",
    "ioc_query_work_orders": "query.work_order",
    "ioc_analyze_summary": "analysis.ioc_summary",
}


def _internal_context() -> ToolContext:
    return ToolContext(caller_type="internal")


def execute_query_tool(capability: str, filters: dict[str, Any] | None = None) -> str:
    result = execute_tool(capability, filters or {}, _internal_context())
    return result.model_dump_json(indent=2, exclude_none=True)


def execute_analysis_tool(
    kpi_data: dict[str, Any] | None = None,
    alarm_data: dict[str, Any] | None = None,
    risk_data: dict[str, Any] | None = None,
    work_order_data: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
) -> str:
    merged_filters = filters or {}
    if kpi_data is not None:
        merged_filters["kpi_data"] = kpi_data
    if alarm_data is not None:
        merged_filters["alarm_data"] = alarm_data
    if risk_data is not None:
        merged_filters["risk_data"] = risk_data
    if work_order_data is not None:
        merged_filters["work_order_data"] = work_order_data
    result = execute_tool("analysis.ioc_summary", merged_filters, _internal_context())
    return result.model_dump_json(indent=2, exclude_none=True)
