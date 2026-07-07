"""QueryOperationDataNode - query operation data through Tool Center."""

from typing import Any

from app.operation_agent.state import OperationState
from app.tool_center.core.schemas import BaseToolInput, ToolContext, ToolResult
from app.tool_center.registry import get_tool

_SUPPORTED_DOMAINS = {"safety", "maintenance", "business", "capability", "all"}
_QUERY_TOOLS = {
    "kpi": "kpi_query",
    "alarm": "alarm_query",
    "risk": "risk_query",
    "work_order": "work_order_query",
}
_DOMAIN_SNAPSHOTS: dict[str, list[dict[str, Any]]] = {
    "business": [
        {
            "metric_code": "operation_improvement_rate",
            "metric_name": "经营改善完成率",
            "value": 86.4,
            "unit": "%",
            "status": "warning",
        },
        {
            "metric_code": "customer_satisfaction_rate",
            "metric_name": "客户满意度",
            "value": 92.3,
            "unit": "%",
            "status": "normal",
        },
        {
            "metric_code": "contract_fulfillment_rate",
            "metric_name": "合同履约率",
            "value": 95.1,
            "unit": "%",
            "status": "warning",
        },
        {
            "metric_code": "low_score_customer_count",
            "metric_name": "低评分客户数",
            "value": 3,
            "unit": "户",
            "status": "warning",
        },
    ],
    "capability": [
        {
            "metric_code": "personnel_certificate_rate",
            "metric_name": "人员持证上岗率",
            "value": 30.81,
            "unit": "%",
            "status": "critical",
        },
        {
            "metric_code": "employee_efficiency",
            "metric_name": "人均处理工单",
            "value": 18.6,
            "unit": "单/人",
            "status": "warning",
        },
        {
            "metric_code": "iot_online_rate",
            "metric_name": "设备在线率",
            "value": 96.2,
            "unit": "%",
            "status": "warning",
        },
        {
            "metric_code": "uncertified_company_count",
            "metric_name": "持证未达标企业数",
            "value": 13,
            "unit": "家",
            "status": "critical",
        },
    ],
}


def query_operation_data_node(state: OperationState) -> OperationState:
    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")
    errors: list[dict] = []

    if domain not in _SUPPORTED_DOMAINS:
        errors.append({"node": "query_operation_data", "message": f"暂不支持的领域: {domain}"})
    elif domain in _DOMAIN_SNAPSHOTS:
        _load_domain_snapshot(state, domain)
    else:
        _query_operation_snapshot(state, errors)

    state["errors"] = state.get("errors", []) + errors
    return state


def _query_operation_snapshot(state: OperationState, errors: list[dict]) -> None:
    raw_data = state.setdefault("raw_data", {})
    raw_data["domain"] = state.get("page_context", {}).get("domain") or state.get("domain", "safety")
    evidence: list[dict[str, Any]] = []
    context = _tool_context(state)
    filters = _build_tool_filters(state)

    tool_data: dict[str, dict[str, Any]] = {}
    for key, tool_name in _QUERY_TOOLS.items():
        result = _run_tool(tool_name, filters.get(key, {}), context, errors)
        if not result or not result.success:
            continue

        data = result.data if isinstance(result.data, dict) else {}
        tool_data[key] = data
        raw_data[key] = data
        raw_data[f"{key}_items"] = data.get("items", [])
        evidence.extend(_serialize_evidence(result, tool_name))

    if tool_data:
        summary = _run_summary_tool(tool_data, context, errors)
        if summary and summary.success and isinstance(summary.data, dict):
            raw_data["ioc_summary"] = summary.data
            evidence.extend(_serialize_evidence(summary, "ioc_summary_analysis"))

    state["metrics"] = _build_metrics(raw_data)
    state["evidence"] = [*state.get("evidence", []), *evidence]


def _load_domain_snapshot(state: OperationState, domain: str) -> None:
    raw_data = state.setdefault("raw_data", {})
    metrics = [
        {
            **item,
            "domain": domain,
            "source": "mock_ioc_domain_snapshot",
        }
        for item in _DOMAIN_SNAPSHOTS[domain]
    ]
    raw_data["domain"] = domain
    raw_data["domain_snapshot"] = {"items": metrics}
    state["metrics"] = metrics
    state["evidence"] = [
        *state.get("evidence", []),
        *[
            {
                "source": "mock_ioc_domain_snapshot",
                "source_type": "domain_metric",
                "record_id": item["metric_code"],
                "description": (
                    f"领域指标: {item['metric_name']}, 值: {item['value']}{item['unit']}, "
                    f"状态: {item['status']}"
                ),
            }
            for item in metrics
        ],
    ]


def _run_tool(
    tool_name: str,
    filters: dict[str, Any],
    context: ToolContext,
    errors: list[dict],
) -> ToolResult | None:
    try:
        tool = get_tool(tool_name)
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"获取 {tool_name} Tool 失败: {e}"})
        return None

    try:
        result = tool.run(BaseToolInput(context=context, filters=filters))
        if not result.success:
            errors.append(
                {
                    "node": "query_operation_data",
                    "message": f"{tool_name} 调用失败: {_tool_error_message(result)}",
                }
            )
        return result
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"{tool_name} 调用异常: {e}"})
        return None


def _run_summary_tool(
    tool_data: dict[str, dict[str, Any]],
    context: ToolContext,
    errors: list[dict],
) -> ToolResult | None:
    return _run_tool(
        "ioc_summary_analysis",
        {
            "kpi_data": tool_data.get("kpi", {}),
            "alarm_data": tool_data.get("alarm", {}),
            "risk_data": tool_data.get("risk", {}),
            "work_order_data": tool_data.get("work_order", {}),
        },
        context,
        errors,
    )


def _tool_context(state: OperationState) -> ToolContext:
    user_context = state.get("user_context", {})
    return ToolContext(
        user_id=user_context.get("user_id") or user_context.get("userId"),
        tenant_id=user_context.get("tenant_id") or user_context.get("tenantId"),
        role=user_context.get("role"),
        request_id=state.get("trace_id"),
    )


def _build_tool_filters(state: OperationState) -> dict[str, dict[str, Any]]:
    page = state.get("page_context", {})
    domain = page.get("domain") or state.get("domain", "safety")
    department = page.get("department")
    filters: dict[str, dict[str, Any]] = {key: {} for key in _QUERY_TOOLS}

    if domain == "safety" and not department:
        filters["kpi"]["department"] = "安全环保部"
        filters["alarm"]["alarm_type"] = "safety"
        filters["risk"]["department"] = "安全环保部"
        filters["work_order"]["department"] = "安全环保部"
    elif domain == "maintenance" and not department:
        filters["kpi"]["department"] = "生产运维部"
        filters["alarm"]["alarm_type"] = "equipment"
        filters["risk"]["department"] = "生产运维部"
        filters["work_order"]["department"] = "生产运维部"
    elif department:
        for item in filters.values():
            item["department"] = department

    time_range = page.get("time_range")
    if time_range in {"today", "yesterday"}:
        filters["kpi"]["time_range"] = time_range
    elif page.get("time_dimension") == "day":
        filters["kpi"]["time_range"] = "today"

    return filters


def _serialize_evidence(result: ToolResult, tool_name: str) -> list[dict[str, Any]]:
    serialized = []
    for ev in result.evidence:
        payload = ev.model_dump()
        payload["tool_name"] = tool_name
        payload["tool_trace_id"] = result.trace_id
        serialized.append(payload)
    return serialized


def _tool_error_message(result: ToolResult) -> str:
    if result.error:
        return f"{result.error.code}: {result.error.message}"
    return "未知 Tool 错误"


def _build_metrics(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = []
    domain = raw_data.get("domain", "safety")

    for item in raw_data.get("kpi_items", []):
        metrics.append(
            {
                "domain": domain,
                "metric_code": item.get("metric_code", ""),
                "metric_name": item.get("metric_name", ""),
                "value": item.get("value"),
                "unit": item.get("unit", ""),
                "status": item.get("status", ""),
                "department": item.get("department"),
                "time_range": item.get("time_range"),
                "source": "kpi_query",
            }
        )

    alarms = raw_data.get("alarm_items", [])
    risks = raw_data.get("risk_items", [])
    work_orders = raw_data.get("work_order_items", [])

    active_alarms = [a for a in alarms if a.get("status") in {"open", "processing"}]
    high_alarms = [a for a in active_alarms if a.get("alarm_level") in {"high", "critical"}]
    pending_risks = [r for r in risks if r.get("status") == "pending"]
    pending_work_orders = [w for w in work_orders if w.get("status") == "pending"]
    in_progress_work_orders = [w for w in work_orders if w.get("status") == "in_progress"]

    metrics.extend(
        [
            _derived_metric(
                "active_alarm_count",
                "未闭环告警数",
                len(active_alarms),
                "条",
                "warning" if active_alarms else "normal",
                "alarm_query",
                domain=domain,
            ),
            _derived_metric(
                "high_alarm_count",
                "高等级未闭环告警数",
                len(high_alarms),
                "条",
                "critical" if high_alarms else "normal",
                "alarm_query",
                domain=domain,
            ),
            _derived_metric(
                "pending_risk_count",
                "待整改隐患数",
                len(pending_risks),
                "项",
                "warning" if pending_risks else "normal",
                "risk_query",
                domain=domain,
            ),
            _derived_metric(
                "pending_work_order_count",
                "待处理工单数",
                len(pending_work_orders),
                "张",
                "warning" if pending_work_orders else "normal",
                "work_order_query",
                domain=domain,
            ),
            _derived_metric(
                "in_progress_work_order_count",
                "处理中工单数",
                len(in_progress_work_orders),
                "张",
                "normal",
                "work_order_query",
                domain=domain,
            ),
        ]
    )

    return metrics


def _derived_metric(
    code: str,
    name: str,
    value: int,
    unit: str,
    status: str,
    source: str,
    domain: str = "safety",
) -> dict[str, Any]:
    return {
        "domain": domain,
        "metric_code": code,
        "metric_name": name,
        "value": value,
        "unit": unit,
        "status": status,
        "source": source,
        "derived": True,
    }
