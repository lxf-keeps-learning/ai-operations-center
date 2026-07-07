from app.operation_agent.state import OperationState
from app.tool_center.core.schemas import BaseToolInput
from app.tool_center.registry import get_tool


def query_operation_data_node(state: OperationState) -> OperationState:
    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")
    errors: list[dict] = []

    if domain == "safety":
        _query_safety_data(state, errors)
    else:
        errors.append({"node": "query_operation_data", "message": f"暂不支持的领域: {domain}"})

    state["errors"] = state.get("errors", []) + errors
    return state


def _query_safety_data(state: OperationState, errors: list[dict]) -> None:
    try:
        kpi_tool = get_tool("kpi_query")
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"获取 kpi_query Tool 失败: {e}"})
        return

    page = state.get("page_context", {})
    filters = {}
    if page.get("department"):
        filters["department"] = page["department"]
    if page.get("date"):
        filters["time_range"] = "today"

    try:
        kpi_result = kpi_tool.run(BaseToolInput(filters=filters))
        if not kpi_result.success:
            errors.append({"node": "query_operation_data", "message": f"KPI 查询失败: {kpi_result.error}"})
            return
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"KPI 查询异常: {e}"})
        return

    items = kpi_result.data.get("items", []) if kpi_result.data else []
    metrics = []
    evidence = []
    for item in items:
        metrics.append({
            "metric_code": item.get("metric_code", ""),
            "metric_name": item.get("metric_name", ""),
            "value": item.get("value"),
            "unit": item.get("unit", ""),
            "status": item.get("status", ""),
        })
    for ev in kpi_result.evidence:
        evidence.append({
            "source": ev.source,
            "source_type": ev.source_type,
            "record_id": ev.record_id,
            "description": ev.description,
        })

    state["raw_data"]["kpi_items"] = items
    state["metrics"] = metrics
    state["evidence"] = evidence
