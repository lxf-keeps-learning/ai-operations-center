from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.prompt_center.application import prompt_version_service
from app.modules.prompt_center.schemas.prompt_schema import PromptVersionSummary
from app.modules.prompt_center.schemas.version_schema import (
    ReviewerAction,
    VersionCompareResponse,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)

router = APIRouter(prefix="/prompts/{prompt_id}/versions", tags=["Prompt 版本"])


@router.get("")
def list_versions(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[list[PromptVersionSummary]]:
    result = prompt_version_service.get_versions_by_prompt(db, prompt_id)
    return success_response(data=result)


@router.post("")
def create_version(
    prompt_id: int,
    data: VersionCreate,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.create_version(db, prompt_id, data)
    return success_response(data=result, message="版本创建成功")


@router.get("/{version_id}")
def get_version(
    prompt_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.get_version(db, version_id)
    return success_response(data=result)


@router.put("/{version_id}")
def update_version(
    prompt_id: int,
    version_id: int,
    data: VersionUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.update_version(db, version_id, data)
    return success_response(data=result, message="版本更新成功")


@router.post("/{version_id}/submit")
def submit_version(
    prompt_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.submit_version(db, version_id)
    return success_response(data=result, message="已提交审核")


@router.post("/{version_id}/approve")
def approve_version(
    prompt_id: int,
    version_id: int,
    action: ReviewerAction,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.approve_version(db, version_id, action.operator_id)
    return success_response(data=result, message="审核通过")


@router.post("/{version_id}/reject")
def reject_version(
    prompt_id: int,
    version_id: int,
    action: ReviewerAction,
    db: Session = Depends(get_db),
) -> ApiResponse[VersionResponse]:
    result = prompt_version_service.reject_version(db, version_id, action.operator_id)
    return success_response(data=result, message="已驳回")
