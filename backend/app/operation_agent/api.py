from fastapi import APIRouter

from app.core.schema.response_schema import ApiResponse
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.schemas.response import OperationAnalyzeResponse
from app.operation_agent.service import analyze_operation

router = APIRouter()


@router.post("/operation/analyze", response_model=ApiResponse[OperationAnalyzeResponse])
def operation_analyze(payload: OperationAnalyzeRequest) -> ApiResponse[OperationAnalyzeResponse]:
    result = analyze_operation(payload)

    abnormal = result.get("abnormal_items", [])
    risk = result.get("risk_items", [])
    advice = result.get("advice_items", [])
    evidence = result.get("evidence", [])
    errors = result.get("errors", [])
    final_answer = result.get("final_answer", "")

    status = "failed" if errors and not final_answer else "partial" if errors else "success"

    data = OperationAnalyzeResponse(
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
