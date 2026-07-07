"""
OperationService — 运营分析业务入口。

职责：
1. 对 API 层屏蔽 Graph 的细节。
2. 将外部请求（OperationAnalyzeRequest）转换为内部 State。
3. 调用 OperationGraph.invoke() 执行分析流程。
4. 返回完整的 OperationState 供 API 层提取结果。
"""
from app.operation_agent.graph import operation_graph
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.state import OperationState


def analyze_operation(request: OperationAnalyzeRequest, user_context: dict | None = None) -> OperationState:
    """
    执行一次运营分析。

    参数：
        request:      前端传入的分析请求（trigger_type、domain、时间维度等）
        user_context: 用户身份信息（由 API 层传入，当前为预留字段）

    返回：
        OperationState — 完整的分析结果，包含：
        - trace_id、final_answer（Markdown）
        - abnormal_items、advice_items、evidence
        - errors（异常记录，不影响返回）

    调用链路：
        API → analyze_operation() → graph.invoke() → 6 个 Node 顺序执行
    """
    # 构造初始 State：只有输入参数，其余字段由各 Node 填充
    initial_state: OperationState = {
        "trigger_type": request.trigger_type,
        "user_question": request.user_question,
        "user_context": user_context or {},
        "page_context": {
            "domain": request.domain,
            "active_tab": request.active_tab,
            "time_dimension": request.time_dimension,
            "date": request.date,
            "company_id": request.company_id,
            "project_id": request.project_id,
        },
    }

    # 执行 Graph（同步调用，内部会串行执行 6 个 Node）
    result = operation_graph.invoke(initial_state)
    return result
