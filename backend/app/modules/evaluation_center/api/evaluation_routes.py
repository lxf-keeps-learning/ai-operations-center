from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.evaluation_center.application.evaluation_service import evaluation_service
from app.modules.evaluation_center.application.metric_service import calculate_metrics, get_metrics_summary
from app.modules.evaluation_center.infrastructure.repositories import evaluation_result_repo
from app.modules.evaluation_center.schemas.evaluation_schema import (
    EvaluateRequest,
    EvaluationMetricsResponse,
    EvaluationResultResponse,
    EvaluatorInfo,
    FailureItem,
    TrendItem,
)
from app.schemas.common import PaginatedResult

router = APIRouter(prefix="/evaluation", tags=["Evaluation 评估中心"])


@router.post("/evaluate")
def evaluate(
    data: EvaluateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[list[EvaluationResultResponse]]:
    results = evaluation_service.evaluate(db, data)
    return success_response(data=results, message="评估完成")


@router.get("/prompts/{prompt_key}/metrics")
def get_prompt_metrics(
    prompt_key: str,
    db: Session = Depends(get_db),
) -> ApiResponse[EvaluationMetricsResponse]:
    metrics = get_metrics_summary(db, prompt_key)
    return success_response(data=EvaluationMetricsResponse(**metrics))


@router.get("/prompts/{prompt_key}/trends")
def get_prompt_trends(
    prompt_key: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> ApiResponse[list[TrendItem]]:
    trend = evaluation_result_repo.get_recent_trend(db, prompt_key, days=days)
    return success_response(data=[TrendItem(**t) for t in trend])


@router.get("/prompts/{prompt_key}/failures")
def get_prompt_failures(
    prompt_key: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> ApiResponse[list[FailureItem]]:
    failures = evaluation_result_repo.get_failure_distribution(db, prompt_key, days=days)
    return success_response(data=[FailureItem(**f) for f in failures])


@router.get("/prompts/{prompt_key}/results")
def list_results(
    prompt_key: str,
    evaluator_key: str | None = Query(None),
    passed: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[PaginatedResult[EvaluationResultResponse]]:
    items, total = evaluation_service.get_results_by_prompt(
        db, prompt_key, evaluator_key=evaluator_key, passed=passed,
        page=page, page_size=page_size,
    )
    return success_response(data=PaginatedResult(items=items, total=total, page=page, page_size=page_size))


@router.get("/results/{result_id}")
def get_result(
    result_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[EvaluationResultResponse]:
    record = evaluation_result_repo.get_by_id(db, result_id)
    if record is None:
        from app.modules.evaluation_center.domain.exceptions import evaluation_not_found
        raise evaluation_not_found(result_id)
    return success_response(data=EvaluationResultResponse.model_validate(record))


@router.get("/results/by-trace/{trace_id}")
def get_results_by_trace(
    trace_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[list[EvaluationResultResponse]]:
    results = evaluation_service.get_results_by_trace(db, trace_id)
    return success_response(data=results)


@router.get("/evaluators")
def list_evaluators() -> ApiResponse[list[EvaluatorInfo]]:
    return success_response(data=[
        EvaluatorInfo(key="json_format", name="JSON 格式", type="deterministic", description="检查模型输出是否为合法 JSON"),
        EvaluatorInfo(key="schema_compliance", name="Schema 合规", type="deterministic", description="检查输出是否符合 JSON Schema"),
        EvaluatorInfo(key="field_completeness", name="字段完整性", type="deterministic", description="检查必填字段是否存在"),
        EvaluatorInfo(key="enum_check", name="枚举值检查", type="deterministic", description="检查枚举字段值是否合法"),
        EvaluatorInfo(key="response_length", name="响应长度", type="deterministic", description="检查响应长度是否在合理范围"),
        EvaluatorInfo(key="question_answered", name="回答问题", type="llm_judge", description="检查 AI 是否回答了用户问题"),
        EvaluatorInfo(key="data_grounded", name="基于数据", type="llm_judge", description="检查 AI 是否基于输入数据回答"),
        EvaluatorInfo(key="no_hallucination", name="无虚构", type="llm_judge", description="检查 AI 是否虚构数据"),
        EvaluatorInfo(key="evidence_provided", name="提供依据", type="llm_judge", description="检查 AI 是否为结论提供依据"),
        EvaluatorInfo(key="actionable_advice", name="可执行建议", type="llm_judge", description="检查建议是否具体可执行"),
    ])


@router.post("/prompts/{prompt_key}/calculate-metrics")
def refresh_metrics(
    prompt_key: str,
    db: Session = Depends(get_db),
) -> ApiResponse[EvaluationMetricsResponse]:
    metrics = calculate_metrics(db, prompt_key)
    return success_response(data=EvaluationMetricsResponse(**metrics))
