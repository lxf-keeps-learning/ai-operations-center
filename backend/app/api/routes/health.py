"""
健康检查接口 — GET /health

返回服务运行状态、环境名称、版本号、数据库/Redis/LLM 状态。
用于前后端联调验证、负载均衡健康检查、部署验证。
"""

from fastapi import APIRouter

from app.core.config.settings import settings
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse[dict], summary="服务健康检查")
async def health_check() -> ApiResponse[dict]:
    redis_status = "CONFIGURED" if settings.redis_enabled else "DISABLED"
    return ApiResponse(
        data={
            "status": "UP",
            "env": settings.app_env,
            "version": settings.version,
            "database": "MOCK",
            "redis": redis_status,
            "llm": "MOCK",
        }
    )
