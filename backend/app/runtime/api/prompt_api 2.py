from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.prompt_schema import PromptCreate, PromptResponse, PromptStatusUpdate
from app.runtime.services.prompt_service import prompt_service
from app.core.schema.response_schema import ApiResponse
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import NOT_FOUND
from app.runtime.repositories.prompt_repository import PromptRepository

router = APIRouter()
_repo = PromptRepository()


@router.post("/runtime/prompts", response_model=ApiResponse[PromptResponse], status_code=201)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)) -> ApiResponse[PromptResponse]:
    result = prompt_service.create(db, payload)
    return ApiResponse(data=result)


@router.get("/runtime/prompts/{code}/active", response_model=ApiResponse[PromptResponse])
def get_active_prompt(code: str, db: Session = Depends(get_db)) -> ApiResponse[PromptResponse]:
    result = prompt_service.get_active_by_code(db, code)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)


@router.get("/runtime/prompts/{code}/versions", response_model=ApiResponse[list[PromptResponse]])
def get_prompt_versions(code: str, db: Session = Depends(get_db)) -> ApiResponse[list[PromptResponse]]:
    results = prompt_service.get_versions_by_code(db, code)
    return ApiResponse(data=results)


@router.patch("/runtime/prompts/{prompt_id}/status", response_model=ApiResponse[PromptResponse])
def update_prompt_status(prompt_id: str, payload: PromptStatusUpdate, db: Session = Depends(get_db)) -> ApiResponse[PromptResponse]:
    result = _repo.update_status(db, prompt_id, payload.status)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    response = PromptResponse.model_validate(result)
    return ApiResponse(data=response)
