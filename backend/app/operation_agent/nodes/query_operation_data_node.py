"""
QueryOperationDataNode — 通过 Tool Center 查询运营数据。

职责：
1. 根据 page_context 中的 domain 确定查询数据类型。
2. 通过 Tool Center 的 kpi_query Tool 获取 KPI 指标数据。
3. 将结果转换为结构化的 metrics 列表，并保留 evidence 链。
4. 查询失败时不崩溃，将错误写入 state.errors。

当前第一版只实现了 safety（本质安全）领域的数据查询。
后续需要扩展 maintenance、business、all 等领域的查询逻辑。

该节点不调用 LLM，直接调用 Tool Center 的 Query Tool。
"""
from app.operation_agent.state import OperationState
from app.tool_center.core.schemas import BaseToolInput
from app.tool_center.registry import get_tool


def query_operation_data_node(state: OperationState) -> OperationState:
    """
    查询运营数据并写入 state。

    safety 领域：通过 kpi_query Tool 查询 KPI 指标。
    其他领域：当前写入 error，返回空 metrics。
    """
    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")
    errors: list[dict] = []

    if domain == "safety":
        _query_safety_data(state, errors)
    else:
        errors.append({"node": "query_operation_data", "message": f"暂不支持的领域: {domain}"})

    state["errors"] = state.get("errors", []) + errors
    return state


def _query_safety_data(state: OperationState, errors: list[dict]) -> None:
    """
    查询 safety 领域的 KPI 数据。

    通过 Tool Center 获取 kpi_query Tool，传入页面筛选条件，
    返回指标数据和 evidence 链。
    """
    # 获取 Tool Center 中的 kpi_query Tool（在 main.py 启动时已注册）
    try:
        kpi_tool = get_tool("kpi_query")
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"获取 kpi_query Tool 失败: {e}"})
        return

    # 从页面上下文构建过滤条件
    page = state.get("page_context", {})
    filters = {}
    if page.get("department"):
        filters["department"] = page["department"]
    if page.get("date"):
        filters["time_range"] = "today"

    # 调用 Tool Center 的 KPI Query Tool
    try:
        kpi_result = kpi_tool.run(BaseToolInput(filters=filters))
        if not kpi_result.success:
            errors.append({"node": "query_operation_data", "message": f"KPI 查询失败: {kpi_result.error}"})
            return
    except Exception as e:
        errors.append({"node": "query_operation_data", "message": f"KPI 查询异常: {e}"})
        return

    # 将 ToolResult 转换为 metrics 列表
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
    # 保留 Tool Center 返回的 evidence 链
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
