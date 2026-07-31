from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import success_response, ApiResponse
from app.db.session import get_db
from app.modules.prompt_center.application import prompt_service
from app.modules.prompt_center.application import prompt_version_service
from app.modules.prompt_center.schemas.prompt_schema import (
    PromptCreate,
    PromptDetailResponse,
    PromptMetricsResponse,
    PromptResponse,
    PromptUpdate,
)
from app.modules.prompt_center.schemas.version_schema import VersionCompareResponse
from app.schemas.common import PaginatedResult

router = APIRouter(prefix="/prompts", tags=["Prompt 管理"])


@router.get("")
def list_prompts(
    search: str | None = Query(None, description="搜索关键词"),
    business_scene: str | None = Query(None, description="业务场景"),
    graph_name: str | None = Query(None, description="所属 Graph"),
    node_name: str | None = Query(None, description="所属 Node"),
    status: str | None = Query(None, description="状态"),
    owner_id: str | None = Query(None, description="负责人"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[PaginatedResult[PromptResponse]]:
    items, total = prompt_service.list_prompts(
        db, search=search, business_scene=business_scene,
        graph_name=graph_name, node_name=node_name,
        status=status, owner_id=owner_id,
        page=page, page_size=page_size,
    )
    return success_response(data=PaginatedResult(items=items, total=total, page=page, page_size=page_size))


@router.post("")
def create_prompt(
    data: PromptCreate,
    db: Session = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    result = prompt_service.create_prompt(db, data)
    return success_response(data=result, message="Prompt 创建成功")


@router.get("/{prompt_id}")
def get_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[PromptDetailResponse]:
    result = prompt_service.get_prompt(db, prompt_id)
    return success_response(data=result)


@router.put("/{prompt_id}")
def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    result = prompt_service.update_prompt(db, prompt_id, data)
    return success_response(data=result, message="Prompt 更新成功")


@router.delete("/{prompt_id}")
def delete_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    prompt_service.delete_prompt(db, prompt_id)
    return success_response(message="Prompt 已删除")


@router.get("/{prompt_id}/metrics")
def get_prompt_metrics(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[PromptMetricsResponse]:
    from app.modules.prompt_center.application.prompt_evaluation_service import get_compliance_stats
    from app.modules.prompt_center.infrastructure.repositories import prompt_def_repo, prompt_test_run_repo

    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    stats = get_compliance_stats(db, prompt_id)

    runs, _ = prompt_test_run_repo.get_by_prompt(db, prompt_id, limit=100)
    avg_tokens = 0
    avg_latency = 0.0
    total_runs = len(runs)
    total_failures = sum(1 for r in runs if r.status == "failed")
    if runs:
        tokens_list = [r.token_usage.get("total_tokens", 0) for r in runs if r.token_usage]
        latencies = [r.latency for r in runs if r.latency]
        avg_tokens = int(sum(tokens_list) / len(tokens_list)) if tokens_list else 0
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return success_response(data=PromptMetricsResponse(
        prompt_id=prompt_id,
        prompt_key=prompt.prompt_key if prompt else "",
        compliance_rate=stats.get("rate"),
        format_compliance=None,
        no_fabrication_rate=None,
        evidence_complete_rate=None,
        avg_tokens=avg_tokens,
        avg_latency_ms=avg_latency,
        total_runs=total_runs,
        total_failures=total_failures,
    ))


@router.get("/{prompt_id}/evaluation-trend")
def get_evaluation_trend(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[list]:
    from app.modules.prompt_center.application.prompt_evaluation_service import get_compliance_stats
    stats = get_compliance_stats(db, prompt_id)
    return success_response(data=[stats])


@router.get("/{prompt_id}/online-failures")
def get_online_failures(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[list]:
    from app.modules.prompt_center.infrastructure.repositories import prompt_test_run_repo
    runs, _ = prompt_test_run_repo.get_by_prompt(db, prompt_id, limit=50)
    failures = [r for r in runs if r.status == "failed"]
    return success_response(data=[
        {"id": r.id, "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in failures
    ])


@router.get("/{prompt_id}/compare")
def compare_versions(
    prompt_id: int,
    source_version_id: int = Query(..., description="源版本 ID"),
    target_version_id: int = Query(..., description="目标版本 ID"),
    db: Session = Depends(get_db),
) -> ApiResponse[VersionCompareResponse]:
    result = prompt_version_service.compare_versions(
        db,
        source_version_id,
        target_version_id,
        prompt_id=prompt_id,
    )
    return success_response(data=result)
