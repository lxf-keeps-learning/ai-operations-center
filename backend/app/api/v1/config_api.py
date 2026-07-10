"""
配置展示接口 — 模型配置 / 运行环境

提供两个接口供前端 Infra Console 页面使用：
  GET /config/models    返回所有已启用 Provider 的非敏感配置（不含 API Key）
  GET /config/runtime   返回当前环境、应用名、版本号、默认模型等运行时信息
"""

from fastapi import APIRouter

from app.core.config.llm_settings import llm_settings
from app.core.config.settings import settings
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.get("/config/models", summary="模型配置列表")
async def get_models() -> ApiResponse[list[dict]]:
    return ApiResponse(data=llm_settings.list_public())


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
