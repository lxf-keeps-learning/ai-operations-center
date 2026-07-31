from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.failure_center.application.failure_service import failure_service
from app.modules.failure_center.schemas.failure_schema import (
    AnalyzeRequest,
    CollectRequest,
    FailureDetailResponse,
    FailureListResponse,
    FailureStatsResponse,
    StatusUpdate,
)
from app.schemas.common import PaginatedResult

router = APIRouter(prefix="/failures", tags=["Failure 失败案例中心"])


@router.post("/collect")
def collect_failures(
    data: CollectRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[list[FailureDetailResponse]]:
    results = failure_service.collect_from_evaluation(db, data)
    return success_response(data=results, message=f"收集到 {len(results)} 个失败案例")


@router.post("/auto-collect/{prompt_key}")
def auto_collect(
    prompt_key: str,
    db: Session = Depends(get_db),
) -> ApiResponse[list[FailureDetailResponse]]:
    results = failure_service.auto_collect(db, prompt_key)
    return success_response(data=results, message=f"自动收集到 {len(results)} 个失败案例")


@router.get("")
def list_failures(
    prompt_key: str | None = Query(None),
    failure_type: str | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[PaginatedResult[FailureListResponse]]:
    items, total = failure_service.list_failures(
        db, prompt_key=prompt_key, failure_type=failure_type,
        status=status, severity=severity, page=page, page_size=page_size,
    )
    return success_response(data=PaginatedResult(items=items, total=total, page=page, page_size=page_size))


@router.get("/{failure_id}")
def get_failure(
    failure_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[FailureDetailResponse]:
    result = failure_service.get_failure(db, failure_id)
    return success_response(data=result)


@router.post("/{failure_id}/convert")
def convert_failure(
    failure_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[FailureDetailResponse]:
    result = failure_service.convert_to_case(db, failure_id)
    return success_response(data=result, message="已转换为测试用例")


@router.post("/{failure_id}/analyze")
def analyze_failure(
    failure_id: int,
    data: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[FailureDetailResponse]:
    result = failure_service.analyze_failure(db, failure_id, data.analysis)
    return success_response(data=result, message="分析已保存")


@router.patch("/{failure_id}/status")
def update_failure_status(
    failure_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[FailureDetailResponse]:
    result = failure_service.update_status(db, failure_id, data.status)
    return success_response(data=result, message="状态已更新")


@router.get("/stats/{prompt_key}")
def get_failure_stats(
    prompt_key: str,
    db: Session = Depends(get_db),
) -> ApiResponse[FailureStatsResponse]:
    result = failure_service.get_stats(db, prompt_key)
    return success_response(data=result)
