from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_adapter.tools import MCP_TOOL_MAP, execute_analysis_tool, execute_query_tool
from app.tool_center.contracts import ToolContext
from app.tool_center.exceptions import CapabilityUnavailableError
from app.tool_registry.compat import discover_tools
from app.tool_registry.contracts import ToolDescriptor

MCP_SERVER_NAME = "AIOperationsCenter MCP Server"

_ANALYSIS_MCP_NAME = "ioc_analyze_summary"

_INSTRUCTIONS = (
    "提供智能运营中心（IOC）的数据查询与聚合分析能力，"
    "包括 KPI 指标、告警、隐患风险、工单查询以及综合聚合分析。"
)


def build_mcp_server() -> FastMCP:
    """从 Registry 描述构建 MCP Server。

    公共工具名保持稳定（MCP_TOOL_MAP），名称与描述来自 Registry 当前选定的版本。
    database 模式下任一能力缺失或发现不可用都会抛异常，使应用启动失败，
    而不是静默暴露未治理的工具。
    """
    descriptors = {
        descriptor.capability: descriptor
        for descriptor in discover_tools(ToolContext(caller_type="internal"))
    }
    server = FastMCP(name=MCP_SERVER_NAME, instructions=_INSTRUCTIONS)
    for mcp_name, capability in MCP_TOOL_MAP.items():
        descriptor = descriptors.get(capability)
        if descriptor is None:
            raise CapabilityUnavailableError(capability)
        if mcp_name == _ANALYSIS_MCP_NAME:
            server.add_tool(
                _analysis_tool_fn(),
                name=mcp_name,
                description=descriptor.description,
            )
        else:
            server.add_tool(
                _query_tool_fn(capability),
                name=mcp_name,
                description=descriptor.description,
            )
    return server


def _query_tool_fn(capability: str) -> Callable[..., str]:
    def query(filters: dict[str, Any] | None = None) -> str:
        return execute_query_tool(capability, filters)

    return query


def _analysis_tool_fn() -> Callable[..., str]:
    def analyze_summary(
        kpi_data: dict[str, Any] | None = None,
        alarm_data: dict[str, Any] | None = None,
        risk_data: dict[str, Any] | None = None,
        work_order_data: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        return execute_analysis_tool(
            kpi_data,
            alarm_data,
            risk_data,
            work_order_data,
            filters,
        )

    return analyze_summary


_mcp: FastMCP | None = None


def __getattr__(name: str):
    """惰性构建模块级 mcp 实例，保证 register_all_tools() 先于发现执行。"""
    global _mcp
    if name == "mcp":
        if _mcp is None:
            _mcp = build_mcp_server()
        return _mcp
    raise AttributeError(name)
