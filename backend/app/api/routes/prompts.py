from fastapi import APIRouter, HTTPException

from app.application.agent_service import agent_service
from app.schemas.common import ApiResponse
from app.schemas.prompt import PromptDetail
from app.utils.ids import new_trace_id

router = APIRouter()


@router.get("/{prompt_code}", response_model=ApiResponse[PromptDetail], summary="查询 Prompt")
async def get_prompt(prompt_code: str) -> ApiResponse[PromptDetail]:
    prompt = agent_service.get_prompt(prompt_code)
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")

    return ApiResponse(message="success", traceId=new_trace_id(), data=prompt)
