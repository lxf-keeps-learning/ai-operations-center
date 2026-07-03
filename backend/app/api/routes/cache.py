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
