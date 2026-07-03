from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.core.schema.response_schema import ApiResponse

router = APIRouter()

_MOCK_RECENT_LOGS: list[dict[str, Any]] = [
    {
        "traceId": "trace_20260703_aaa",
        "level": "INFO",
        "path": "/api/v1/health",
        "method": "GET",
        "status": 200,
        "durationMs": 12,
        "time": "2026-07-03T10:00:00",
    },
    {
        "traceId": "trace_20260703_bbb",
        "level": "WARNING",
        "path": "/api/v1/items/99999",
        "method": "GET",
        "status": 404,
        "durationMs": 5,
        "time": "2026-07-03T10:01:00",
    },
    {
        "traceId": "trace_20260703_ccc",
        "level": "INFO",
        "path": "/api/v1/agent/chat",
        "method": "POST",
        "status": 200,
        "durationMs": 2340,
        "time": "2026-07-03T10:02:00",
    },
    {
        "traceId": "trace_20260703_ddd",
        "level": "ERROR",
        "path": "/api/v1/agent/analyze",
        "method": "POST",
        "status": 502,
        "durationMs": 15000,
        "time": "2026-07-03T10:03:00",
    },
]

_MOCK_LLM_LOGS: list[dict[str, Any]] = [
    {
        "traceId": "trace_20260703_ccc",
        "provider": "qwen",
        "model": "qwen-plus",
        "inputTokens": 1200,
        "outputTokens": 800,
        "totalTokens": 2000,
        "durationMs": 2340,
        "success": True,
    },
    {
        "traceId": "trace_20260703_ddd",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "inputTokens": 500,
        "outputTokens": 0,
        "totalTokens": 500,
        "durationMs": 15000,
        "success": False,
        "errorMessage": "LLM 调用超时",
    },
    {
        "traceId": "trace_20260703_eee",
        "provider": "doubao",
        "model": "doubao-pro",
        "inputTokens": 800,
        "outputTokens": 1200,
        "totalTokens": 2000,
        "durationMs": 1800,
        "success": True,
    },
]


@router.get("/logs/recent", summary="最近日志")
async def get_recent_logs() -> ApiResponse[list[dict]]:
    return ApiResponse(data=_MOCK_RECENT_LOGS)


@router.get("/logs/llm-usage", summary="LLM 使用日志")
async def get_llm_usage_logs() -> ApiResponse[list[dict]]:
    return ApiResponse(data=_MOCK_LLM_LOGS)
