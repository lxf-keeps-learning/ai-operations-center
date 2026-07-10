"""
Redis 健康检查接口 — GET /cache/ping

提供 Redis 连接状态检测：
  - REDIS_ENABLED=false 时返回 disabled 状态，不报错
  - REDIS_ENABLED=true 时尝试连接 Redis 并返回 pong
  - 连接失败时返回清晰错误信息，不影响其他接口

Sprint0 阶段 Redis 作为预留组件，不阻塞主流程。
"""

from fastapi import APIRouter

from app.config.settings import settings
from app.core.exception.error_code import REDIS_CONNECTION_ERROR
from app.db.redis import RedisPingError, ping_redis
from app.schemas.cache import CachePingResponse
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/ping", response_model=ApiResponse[CachePingResponse], summary="Redis 健康检查")
def ping_cache() -> ApiResponse[CachePingResponse]:
    if not settings.redis_enabled:
        return ApiResponse(
            message="Redis disabled",
            data=CachePingResponse(
                enabled=False,
                status="disabled",
                message="Redis disabled",
            ),
        )

    try:
        response = ping_redis(settings.redis_url)
    except RedisPingError as exc:
        return ApiResponse(
            code=REDIS_CONNECTION_ERROR.code,
            message=REDIS_CONNECTION_ERROR.message,
            data=CachePingResponse(
                enabled=True,
                status="error",
                message=REDIS_CONNECTION_ERROR.message,
                error=str(exc),
            ),
        )

    return ApiResponse(
        message="pong",
        data=CachePingResponse(
            enabled=True,
            status="up",
            message="pong",
            response=response,
        ),
    )
