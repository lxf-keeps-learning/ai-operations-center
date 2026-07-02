from fastapi import APIRouter

from app.config.settings import settings
from app.schemas.common import ApiResponse
from app.schemas.health import HealthStatus
from app.utils.ids import new_trace_id

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthStatus], summary="服务健康检查")
async def health_check() -> ApiResponse[HealthStatus]:
    trace_id = new_trace_id()
    redis_status = "CONFIGURED" if settings.redis_enabled else "DISABLED"
    return ApiResponse(
        message="success",
        traceId=trace_id,
        data=HealthStatus(status="UP", database="MOCK", redis=redis_status, llm="MOCK"),
    )
