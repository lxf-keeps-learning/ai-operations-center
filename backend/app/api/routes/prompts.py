"""
Prompt 查询接口 — GET /prompts/{prompt_code}

通过 prompt_code 查询系统中预配置的 Prompt 模板。
用于前端需要获取完整 Prompt 内容进行展示或调试的场景。
"""

from fastapi import APIRouter, HTTPException

from app.application.agent_service import agent_service
from app.schemas.common import ApiResponse
from app.schemas.prompt import PromptDetail

router = APIRouter()


@router.get("/{prompt_code}", response_model=ApiResponse[PromptDetail], summary="查询 Prompt")
async def get_prompt(prompt_code: str) -> ApiResponse[PromptDetail]:
    prompt = agent_service.get_prompt(prompt_code)
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")

    return ApiResponse(data=prompt)
