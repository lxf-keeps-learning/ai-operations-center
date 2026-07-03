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
