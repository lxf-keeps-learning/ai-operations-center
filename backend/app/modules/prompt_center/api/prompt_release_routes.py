from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse, success_response
from app.db.session import get_db
from app.modules.prompt_center.application.prompt_render_service import preview_prompt, render_prompt
from app.modules.prompt_center.application.prompt_release_service import (
    get_releases,
    gray_release,
    production_release,
    rollback,
)
from app.modules.prompt_center.schemas.release_schema import (
    PreviewRequest,
    ReleaseRequest,
    ReleaseResponse,
    RenderRequest,
    RenderResponse,
    RollbackRequest,
)

router = APIRouter(tags=["Prompt 发布与渲染"])


@router.post("/prompts/render")
def render_prompt_api(
    data: RenderRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[RenderResponse]:
    result = render_prompt(
        db,
        prompt_key=data.prompt_key,
        environment=data.environment,
        version=data.version,
        variables=data.variables,
        user_question=data.user_question,
    )
    return success_response(data=RenderResponse.model_validate(result))


@router.post("/prompts/{prompt_id}/preview")
def preview_prompt_api(
    prompt_id: int,
    data: PreviewRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[RenderResponse]:
    result = preview_prompt(
        db,
        prompt_id=prompt_id,
        version_id=data.version_id,
        variables=data.variables,
        user_question=data.user_question,
    )
    return success_response(data=RenderResponse.model_validate(result))


@router.post("/prompts/{prompt_id}/versions/{version_id}/gray-release")
def gray_release_api(
    prompt_id: int,
    version_id: int,
    data: ReleaseRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[ReleaseResponse]:
    result = gray_release(db, prompt_id, version_id, data)
    return success_response(data=result, message="灰度发布成功")


@router.post("/prompts/{prompt_id}/versions/{version_id}/publish")
def publish_api(
    prompt_id: int,
    version_id: int,
    data: ReleaseRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[ReleaseResponse]:
    result = production_release(db, prompt_id, version_id, data)
    return success_response(data=result, message="发布成功")


@router.post("/prompts/{prompt_id}/rollback")
def rollback_api(
    prompt_id: int,
    data: RollbackRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[ReleaseResponse | None]:
    result = rollback(db, prompt_id, data)
    return success_response(data=result, message="回滚成功")


@router.get("/prompts/{prompt_id}/releases")
def list_releases(
    prompt_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[list[ReleaseResponse]]:
    result = get_releases(db, prompt_id)
    return success_response(data=result)
