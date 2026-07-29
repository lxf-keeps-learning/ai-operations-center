from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.experiment_center.application.experiment_service import experiment_service
from app.modules.experiment_center.infrastructure.repositories import (
    experiment_result_repo,
)
from app.modules.experiment_center.schemas.experiment_schema import (
    CompareResponse,
    ExperimentCreate,
    ExperimentDetailResponse,
    ExperimentListResponse,
    ExperimentResultRow,
    ExperimentRunResult,
)
from app.schemas.common import PaginatedResult

router = APIRouter(prefix="/experiments", tags=["Experiment 实验中心"])


@router.get("")
def list_experiments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[PaginatedResult[ExperimentListResponse]]:
    items, total = experiment_service.list_experiments(db, page=page, page_size=page_size)
    return success_response(data=PaginatedResult(items=items, total=total, page=page, page_size=page_size))


@router.post("")
def create_experiment(
    data: ExperimentCreate,
    db: Session = Depends(get_db),
) -> ApiResponse[ExperimentDetailResponse]:
    result = experiment_service.create_experiment(db, data)
    return success_response(data=result, message="实验创建成功")


@router.get("/{experiment_id}")
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[ExperimentDetailResponse]:
    result = experiment_service.get_experiment(db, experiment_id)
    return success_response(data=result)


@router.post("/{experiment_id}/run")
def run_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[ExperimentDetailResponse]:
    result = experiment_service.run_experiment(db, experiment_id)
    return success_response(data=result, message="实验运行完成")


@router.get("/{experiment_id}/compare")
def compare_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[CompareResponse]:
    result = experiment_service.compare_versions(db, experiment_id)
    return success_response(data=result)


@router.get("/{experiment_id}/results")
def get_experiment_results(
    experiment_id: int,
    version: str | None = Query(None, description="筛选版本: source/target"),
    db: Session = Depends(get_db),
) -> ApiResponse[list[ExperimentResultRow]]:
    if version:
        records = experiment_result_repo.get_by_experiment_and_version(db, experiment_id, version)
    else:
        records = experiment_result_repo.get_by_experiment(db, experiment_id)
    return success_response(data=[ExperimentResultRow.model_validate(r) for r in records])
