from collections.abc import Callable
import copy
from typing import Any

from jsonschema.validators import validator_for
from mcp.server.fastmcp import FastMCP

from app.mcp_adapter.tools import MCP_TOOL_MAP, execute_analysis_tool, execute_query_tool
from app.tool_center.contracts import ToolContext
from app.tool_center.exceptions import CapabilityUnavailableError, RegistryConfigurationError
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
            _add_registry_tool(
                server,
                _analysis_tool_fn,
                descriptor,
                mcp_name,
            )
        else:
            _add_registry_tool(
                server,
                lambda schema, capability=capability: _query_tool_fn(capability, schema),
                descriptor,
                mcp_name,
            )
    return server


def _query_tool_fn(capability: str, input_schema: dict[str, Any]) -> Callable[..., str]:
    validator = _validator(input_schema)

    def query(filters: dict[str, Any] | None = None) -> str:
        validator.validate({"filters": filters if filters is not None else {}})
        return execute_query_tool(capability, filters)

    return query


def _analysis_tool_fn(input_schema: dict[str, Any]) -> Callable[..., str]:
    validator = _validator(input_schema)

    def analyze_summary(
        kpi_data: dict[str, Any] | None = None,
        alarm_data: dict[str, Any] | None = None,
        risk_data: dict[str, Any] | None = None,
        work_order_data: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        arguments = {
            key: value
            for key, value in {
                "kpi_data": kpi_data,
                "alarm_data": alarm_data,
                "risk_data": risk_data,
                "work_order_data": work_order_data,
                "filters": filters,
            }.items()
            if value is not None
        }
        validator.validate(arguments)
        return execute_analysis_tool(
            kpi_data,
            alarm_data,
            risk_data,
            work_order_data,
            filters,
        )

    return analyze_summary


def _add_registry_tool(
    server: FastMCP,
    function_factory: Callable[[dict[str, Any]], Callable[..., str]],
    descriptor: ToolDescriptor,
    mcp_name: str,
) -> None:
    # 先用 callable 生成框架 schema，再用 Registry schema 校验/覆盖公开边界。
    provisional = function_factory({"type": "object"})
    server.add_tool(provisional, name=mcp_name, description=descriptor.description)
    registered = server._tool_manager.get_tool(mcp_name)
    generated_schema = copy.deepcopy(registered.parameters)
    public_schema = _public_input_schema(descriptor, generated_schema)
    public_properties = set(public_schema.get("properties", {}))
    callable_properties = set(generated_schema.get("properties", {}))
    if public_properties != callable_properties:
        raise RegistryConfigurationError(
            f"Registry input schema is incompatible with MCP callable {mcp_name}: "
            f"registry={sorted(public_properties)} callable={sorted(callable_properties)}"
        )
    for property_name in sorted(public_properties):
        registry_property = public_schema["properties"][property_name]
        callable_property = generated_schema["properties"][property_name]
        registry_types = _json_types(registry_property)
        callable_types = _json_types(callable_property)
        if not registry_types.issubset(callable_types):
            raise RegistryConfigurationError(
                f"Registry input property {property_name} is incompatible with MCP "
                f"callable {mcp_name}: registry={sorted(registry_types)} "
                f"callable={sorted(callable_types)}"
            )

    # Replace the provisional callable with a wrapper that validates the exact Registry schema.
    server._tool_manager._tools.pop(mcp_name, None)
    server.add_tool(
        function_factory(public_schema),
        name=mcp_name,
        description=descriptor.description,
    )
    server._tool_manager.get_tool(mcp_name).parameters = public_schema


def _public_input_schema(
    descriptor: ToolDescriptor,
    generated_schema: dict[str, Any],
) -> dict[str, Any]:
    registry_schema = _thaw_json(descriptor.input_schema)
    validator_for(registry_schema).check_schema(registry_schema)
    properties = registry_schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        # Legacy descriptors were intentionally schemaless; preserve their callable contract.
        return generated_schema

    public_schema = copy.deepcopy(registry_schema)
    public_schema["properties"].pop("context", None)
    required = public_schema.get("required")
    if isinstance(required, list):
        public_schema["required"] = [item for item in required if item != "context"]
        if not public_schema["required"]:
            public_schema.pop("required")
    validator_for(public_schema).check_schema(public_schema)
    return public_schema


def _validator(schema: dict[str, Any]):
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    return validator_type(schema)


_ALL_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)


def _json_types(schema: object) -> frozenset[str]:
    """Return the JSON types accepted by a property schema.

    FastMCP's generated callable schemas use ``anyOf`` for nullable parameters.
    Treat an untyped/complex schema conservatively as accepting every JSON type;
    that makes build-time compatibility fail closed when the callable is narrower.
    """
    if not isinstance(schema, dict):
        return _ALL_JSON_TYPES
    declared = schema.get("type")
    if isinstance(declared, str):
        return frozenset({declared})
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        return frozenset(declared)
    alternatives = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(alternatives, list) and alternatives:
        return frozenset().union(*(_json_types(item) for item in alternatives))
    return _ALL_JSON_TYPES


def _thaw_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_thaw_json(item) for item in value]
    return value


_mcp: FastMCP | None = None


def __getattr__(name: str):
    """惰性构建模块级 mcp 实例，保证 register_all_tools() 先于发现执行。"""
    global _mcp
    if name == "mcp":
        if _mcp is None:
            _mcp = build_mcp_server()
        return _mcp
    raise AttributeError(name)
