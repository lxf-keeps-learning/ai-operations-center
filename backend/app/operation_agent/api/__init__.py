"""
Operation API — 运营分析 HTTP 接口。

路由：POST /api/v1/operation/analyze

职责：
1. 接收前端传入的 OperationAnalyzeRequest。
2. 调用 OperationService.analyze_operation()。
3. 将 OperationState 转换为 OperationAnalyzeResponse 返回。

API 层不包含任何业务分析逻辑、不直接调用 LLM、不直接查询数据库。
"""
from fastapi import APIRouter

from app.core.schema.response_schema import ApiResponse
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.schemas.response import OperationAnalyzeResponse
from app.operation_agent.service import analyze_operation

router = APIRouter()


@router.post("/operation/analyze", response_model=ApiResponse[OperationAnalyzeResponse])
def operation_analyze(payload: OperationAnalyzeRequest) -> ApiResponse[OperationAnalyzeResponse]:
    """
    执行运营分析并返回结果。

    请求体：
        trigger_type:   触发类型（默认 tab_analysis）
        domain:         分析领域（默认 safety，本质安全）
        active_tab:     当前活跃 Tab
        time_dimension: 时间维度（day / week / month）
        date:           分析日期

    返回（统一 ApiResponse 包裹）：
        trace_id        请求追踪 ID
        status          success / partial / failed
        summary         Markdown 格式的运营分析结论
        abnormal_items  异常项列表
        advice_items    改进建议列表
        evidence        数据来源证据
        errors          处理过程中的错误
    """
    # 调用 Service 层（Graph 编排入口）
    result = analyze_operation(payload)

    # 从 State 中提取各字段
    abnormal = result.get("abnormal_items", [])
    risk = result.get("risk_items", [])
    advice = result.get("advice_items", [])
    evidence = result.get("evidence", [])
    errors = result.get("errors", [])
    final_answer = result.get("final_answer", "")

    # 状态判定：有错误但无结论 → failed；有错误但有结论 → partial
    status = "failed" if errors and not final_answer else "partial" if errors else "success"

    # 构造统一响应
    data = OperationAnalyzeResponse(
        record_id=result.get("record_id"),
        trace_id=result.get("trace_id", ""),
        status=status,
        summary=final_answer,
        abnormal_items=abnormal,
        risk_items=risk,
        advice_items=advice,
        evidence=evidence,
        errors=errors,
    )

    return ApiResponse(data=data)
