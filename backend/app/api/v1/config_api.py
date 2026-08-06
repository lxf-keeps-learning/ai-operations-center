"""
配置展示接口 — 模型配置 / 运行环境

提供两个接口供前端 Infra Console 页面使用：
  GET /config/models    返回所有已启用 Provider 的非敏感配置（不含 API Key）
  GET /config/runtime   返回当前环境、应用名、版本号、默认模型等运行时信息
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config.llm_settings import llm_settings
from app.core.config.settings import settings
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


class ModelSelectionRequest(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


@router.get("/config/models", summary="模型配置列表")
async def get_models() -> ApiResponse[list[dict]]:
    return ApiResponse(data=llm_settings.list_public())


@router.put("/config/models/selection", summary="切换默认模型")
async def select_model(payload: ModelSelectionRequest) -> ApiResponse[dict]:
    try:
        selected = llm_settings.select(payload.provider, payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=selected.to_public())


@router.get("/config/runtime", summary="当前运行环境")
async def get_runtime() -> ApiResponse[dict]:
    return ApiResponse(
        data={
            "env": settings.app_env,
            "appName": settings.app_name,
            "version": settings.version,
            "defaultModel": llm_settings.default_provider,
            "timezone": settings.app_timezone,
        }
    )
