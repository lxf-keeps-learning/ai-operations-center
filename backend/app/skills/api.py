"""Runtime Skill 发现与统一执行 API。"""

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.core.context.context_holder import get_request_context, get_user_context
from app.core.schema.response_schema import ApiResponse
from app.skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillExecutionRequest,
    SkillExecutionResult,
)
from app.skills.definitions import skill_registry
from app.skills.executor import execute_skill
from app.skills.registry import SkillNotFoundError

router = APIRouter(tags=["Skills"])


@router.get("/skills", response_model=ApiResponse[list[SkillDefinition]])
def list_skills() -> ApiResponse[list[SkillDefinition]]:
    return ApiResponse(data=skill_registry.list())


@router.get("/skills/{skill_id}", response_model=ApiResponse[SkillDefinition])
def get_skill(skill_id: str) -> ApiResponse[SkillDefinition]:
    try:
        definition = skill_registry.get(skill_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=definition)


@router.post(
    "/skills/{skill_id}/execute",
    response_model=ApiResponse[SkillExecutionResult],
)
def run_skill(
    skill_id: str,
    payload: SkillExecutionRequest,
) -> ApiResponse[SkillExecutionResult]:
    try:
        definition = skill_registry.get(skill_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    user_context = get_user_context()
    context = SkillExecutionContext(
        trace_id=get_request_context().trace_id,
        user_id=user_context.user_id or "anonymous",
        tenant_id=user_context.org_id or None,
        roles=list(user_context.roles),
        permissions=list(user_context.permissions),
    )
    try:
        result = execute_skill(definition, payload.inputs, context)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=result)
