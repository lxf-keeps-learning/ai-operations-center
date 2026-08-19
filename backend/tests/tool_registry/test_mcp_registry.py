from __future__ import annotations

from jsonschema import ValidationError
import pytest
from mcp.server.fastmcp.exceptions import ToolError as FastMCPToolError

from app.mcp_adapter import server as server_module
from app.mcp_adapter import tools as adapter
from app.tool_center.contracts import ToolResult
from app.tool_center.exceptions import RegistryConfigurationError
from app.tool_registry.contracts import ToolDescriptor, ToolType

PUBLIC_MCP_NAMES = {
    "ioc_query_kpi",
    "ioc_query_alarms",
    "ioc_query_risks",
    "ioc_query_work_orders",
    "ioc_analyze_summary",
}


def _descriptor(
    capability: str,
    tool_key: str,
    description: str,
    *,
    input_schema: dict | None = None,
) -> ToolDescriptor:
    return ToolDescriptor(
        tool_id=1,
        tool_key=tool_key,
        capability=capability,
        name=tool_key,
        description=description,
        tool_type=ToolType.QUERY,
        action_phase=None,
        version_id=11,
        version="1.0.0",
        input_schema=input_schema or {"type": "object"},
        output_schema={"type": "object"},
        rate_limit_per_minute=60,
        selected_stable=True,
    )


KPI_DESCRIPTOR = _descriptor("query.kpi", "kpi_query", "注册中心提供的 KPI 描述")
ALARM_DESCRIPTOR = _descriptor("query.alarm", "alarm_query", "注册中心提供的告警描述")
RISK_DESCRIPTOR = _descriptor("query.risk", "risk_query", "注册中心提供的隐患描述")
WORK_ORDER_DESCRIPTOR = _descriptor("query.work_order", "work_order_query", "注册中心提供的工单描述")
ANALYSIS_DESCRIPTOR = _descriptor("analysis.ioc_summary", "ioc_summary_analysis", "注册中心提供的分析描述")


def _registry_descriptors():
    return [
        KPI_DESCRIPTOR,
        ALARM_DESCRIPTOR,
        RISK_DESCRIPTOR,
        WORK_ORDER_DESCRIPTOR,
        ANALYSIS_DESCRIPTOR,
    ]


def _registered_tool(mcp, name):
    return mcp._tool_manager.get_tool(name)


def test_mcp_query_executes_capability(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        calls.append((capability, arguments, context))
        return ToolResult(success=True, data={"total": 3})

    monkeypatch.setattr(adapter, "execute_tool", fake_execute)

    adapter.execute_query_tool("query.kpi", {"department": "安全环保部"})

    assert calls[0][0] == "query.kpi"
    assert calls[0][1] == {"department": "安全环保部"}
    assert calls[0][2].caller_type == "internal"


def test_mcp_analysis_merges_inputs_and_executes_capability(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        calls.append((capability, arguments, context))
        return ToolResult(success=True, data={"risk_score": 0})

    monkeypatch.setattr(adapter, "execute_tool", fake_execute)

    adapter.execute_analysis_tool(kpi_data={"a": 1}, alarm_data={"b": 2})

    assert calls[0][0] == "analysis.ioc_summary"
    assert calls[0][1]["kpi_data"] == {"a": 1}
    assert calls[0][1]["alarm_data"] == {"b": 2}
    assert calls[0][2].caller_type == "internal"


def test_mcp_description_comes_from_registry(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "discover_tools", lambda context: _registry_descriptors())

    mcp = server_module.build_mcp_server()

    assert _registered_tool(mcp, "ioc_query_kpi").description == KPI_DESCRIPTOR.description
    assert _registered_tool(mcp, "ioc_query_alarms").description == ALARM_DESCRIPTOR.description
    assert _registered_tool(mcp, "ioc_analyze_summary").description == ANALYSIS_DESCRIPTOR.description


def test_mcp_public_names_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "discover_tools", lambda context: _registry_descriptors())

    mcp = server_module.build_mcp_server()

    registered = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert registered == PUBLIC_MCP_NAMES


def test_mcp_registered_query_tool_invokes_execute_tool(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "discover_tools", lambda context: _registry_descriptors())
    calls: list[tuple] = []

    def fake_execute(capability, arguments, context, confirmation_token=None, stable_only=False):
        calls.append((capability, arguments, context))
        return ToolResult(success=True, data={"total": 3})

    monkeypatch.setattr(adapter, "execute_tool", fake_execute)
    mcp = server_module.build_mcp_server()

    tool = _registered_tool(mcp, "ioc_query_kpi")
    tool.fn({"department": "安全环保部"})

    assert calls[0][0] == "query.kpi"
    assert calls[0][2].caller_type == "internal"


def test_build_mcp_server_fails_when_capability_missing(monkeypatch) -> None:
    from app.tool_center.exceptions import CapabilityUnavailableError

    monkeypatch.setattr(server_module, "discover_tools", lambda context: [])

    with pytest.raises(CapabilityUnavailableError):
        server_module.build_mcp_server()


@pytest.mark.anyio
async def test_fastmcp_lists_governed_tools(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "discover_tools", lambda context: _registry_descriptors())

    mcp = server_module.build_mcp_server()
    tools = await mcp.list_tools()

    assert {tool.name for tool in tools} == PUBLIC_MCP_NAMES
    kpi = next(tool for tool in tools if tool.name == "ioc_query_kpi")
    assert kpi.description == KPI_DESCRIPTOR.description
    assert kpi.inputSchema["type"] == "object"


@pytest.mark.anyio
async def test_mcp_query_schema_comes_from_registry_and_validates_nested_filters(
    monkeypatch,
) -> None:
    schema = {
        "type": "object",
        "properties": {
            "context": {"type": "object"},
            "filters": {
                "type": "object",
                "properties": {
                    "department": {"type": "string", "minLength": 2},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["department"],
                "additionalProperties": False,
            },
        },
        "required": ["filters"],
        "additionalProperties": False,
    }
    descriptors = [
        _descriptor(
            "query.kpi",
            "kpi_query",
            "strict KPI",
            input_schema=schema,
        ),
        ALARM_DESCRIPTOR,
        RISK_DESCRIPTOR,
        WORK_ORDER_DESCRIPTOR,
        ANALYSIS_DESCRIPTOR,
    ]
    monkeypatch.setattr(server_module, "discover_tools", lambda context: descriptors)

    mcp = server_module.build_mcp_server()
    listed = await mcp.list_tools()
    kpi = next(tool for tool in listed if tool.name == "ioc_query_kpi")

    assert "context" not in kpi.inputSchema["properties"]
    assert kpi.inputSchema["properties"]["filters"]["properties"]["limit"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
    }
    with pytest.raises(FastMCPToolError):
        await _registered_tool(mcp, "ioc_query_kpi").run(
            {"filters": {"department": "A", "limit": 0}}
        )


def test_mcp_query_wrapper_does_not_normalize_invalid_falsy_filters(
    monkeypatch,
) -> None:
    schema = {
        "type": "object",
        "properties": {
            "context": {"type": "object"},
            "filters": {"type": "object"},
        },
        "additionalProperties": False,
    }
    descriptors = [
        _descriptor("query.kpi", "kpi_query", "strict KPI", input_schema=schema),
        ALARM_DESCRIPTOR,
        RISK_DESCRIPTOR,
        WORK_ORDER_DESCRIPTOR,
        ANALYSIS_DESCRIPTOR,
    ]
    monkeypatch.setattr(server_module, "discover_tools", lambda context: descriptors)
    mcp = server_module.build_mcp_server()

    with pytest.raises(ValidationError):
        _registered_tool(mcp, "ioc_query_kpi").fn("")


def test_mcp_build_rejects_registry_schema_incompatible_with_public_callable(
    monkeypatch,
) -> None:
    incompatible = _descriptor(
        "query.kpi",
        "kpi_query",
        "bad KPI",
        input_schema={
            "type": "object",
            "properties": {
                "context": {"type": "object"},
                "unsupported": {"type": "string"},
            },
        },
    )
    monkeypatch.setattr(
        server_module,
        "discover_tools",
        lambda context: [
            incompatible,
            ALARM_DESCRIPTOR,
            RISK_DESCRIPTOR,
            WORK_ORDER_DESCRIPTOR,
            ANALYSIS_DESCRIPTOR,
        ],
    )

    with pytest.raises(RegistryConfigurationError, match="schema|callable"):
        server_module.build_mcp_server()


def test_mcp_build_rejects_registry_property_type_incompatible_with_callable(
    monkeypatch,
) -> None:
    incompatible = _descriptor(
        "query.kpi",
        "kpi_query",
        "bad KPI filter type",
        input_schema={
            "type": "object",
            "properties": {
                "context": {"type": "object"},
                "filters": {"type": "string"},
            },
        },
    )
    monkeypatch.setattr(
        server_module,
        "discover_tools",
        lambda context: [
            incompatible,
            ALARM_DESCRIPTOR,
            RISK_DESCRIPTOR,
            WORK_ORDER_DESCRIPTOR,
            ANALYSIS_DESCRIPTOR,
        ],
    )

    with pytest.raises(RegistryConfigurationError, match="filters|callable"):
        server_module.build_mcp_server()
