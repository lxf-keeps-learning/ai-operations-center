from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.prompt_center.application import prompt_test_service
from app.modules.prompt_center.application.prompt_evaluation_service import (
    get_evaluation_summary,
    run_deterministic_evaluations,
)
from app.modules.prompt_center.schemas.test_schema import (
    DatasetTestRequest,
    EvaluationSummary,
    TestCaseCreate,
    TestCaseResponse,
    TestRunRequest,
    TestRunResponse,
)
from app.modules.prompt_center.schemas.release_schema import RenderRequest, RenderResponse

router = APIRouter(tags=["Prompt 测试"])


@router.get("/prompts/{prompt_id}/test-cases")
def list_test_cases(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[list[TestCaseResponse]]:
    result = prompt_test_service.list_test_cases(db, prompt_id)
    return success_response(data=result)


@router.post("/prompts/{prompt_id}/test-cases")
def create_test_case(
    prompt_id: int,
    data: TestCaseCreate,
    db: Session = Depends(get_db),
) -> ApiResponse[TestCaseResponse]:
    result = prompt_test_service.create_test_case(db, prompt_id, data)
    return success_response(data=result, message="测试用例创建成功")


@router.post("/prompts/{prompt_id}/versions/{version_id}/test")
def run_test(
    prompt_id: int,
    version_id: int,
    data: TestRunRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[TestRunResponse]:
    result = prompt_test_service.run_single_test(db, prompt_id, version_id, data)
    if result.status == "completed":
        run_deterministic_evaluations(db, result.id)
        result = prompt_test_service.get_test_run(db, result.id)
    return success_response(data=result, message="测试完成")


@router.post("/prompts/{prompt_id}/versions/{version_id}/dataset-test")
def run_dataset_test(
    prompt_id: int,
    version_id: int,
    data: DatasetTestRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[list[TestRunResponse]]:
    results = prompt_test_service.run_dataset_test(db, prompt_id, version_id, data)
    for r in results:
        if r.status == "completed":
            run_deterministic_evaluations(db, r.id)
    return success_response(data=results, message="数据集测试完成")


@router.get("/prompts/{prompt_id}/test-runs")
def list_test_runs(
    prompt_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[TestRunResponse]]:
    items, total = prompt_test_service.list_test_runs(db, prompt_id, page, page_size)
    return success_response(data=items)


@router.get("/prompt-test-runs/{run_id}")
def get_test_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[TestRunResponse]:
    result = prompt_test_service.get_test_run(db, run_id)
    return success_response(data=result)


@router.get("/prompt-test-runs/{run_id}/evaluation")
def get_test_run_evaluation(
    run_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[EvaluationSummary]:
    result = get_evaluation_summary(db, run_id)
    return success_response(data=result)
