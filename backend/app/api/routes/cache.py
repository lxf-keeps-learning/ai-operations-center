from fastapi import APIRouter

from app.config.settings import settings
from app.db.redis import RedisPingError, ping_redis
from app.schemas.cache import CachePingResponse
from app.schemas.common import ApiResponse
from app.utils.ids import new_trace_id

router = APIRouter()


@router.get("/ping", response_model=ApiResponse[CachePingResponse], summary="Redis 健康检查")
def ping_cache() -> ApiResponse[CachePingResponse]:
    trace_id = new_trace_id()

    if not settings.redis_enabled:
        return ApiResponse(
            message="Redis disabled",
            traceId=trace_id,
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
            code=5003,
            message="Redis connection failed",
            traceId=trace_id,
            data=CachePingResponse(
                enabled=True,
                status="error",
                message="Redis connection failed",
                error=str(exc),
            ),
        )

    return ApiResponse(
        message="pong",
        traceId=trace_id,
        data=CachePingResponse(
            enabled=True,
            status="up",
            message="pong",
            response=response,
        ),
    )
