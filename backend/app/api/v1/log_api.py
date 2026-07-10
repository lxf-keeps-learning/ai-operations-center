"""
日志查询接口 — 最近日志 / LLM 使用日志

提供两个接口供前端日志中心页面展示：
  GET /logs/recent      最近系统日志（当前使用 Mock 数据）
  GET /logs/llm-usage   最近 LLM 调用记录（Mock 数据，含 provider / model / tokens / success）

现状：
  Sprint1 阶段使用内存 Mock 数据演示日志中心功能，
  后续接入真实日志存储后替换为数据库查询。
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.core.schema.response_schema import ApiResponse

router = APIRouter()

# Sprint1: 使用 Mock 数据演示日志中心，后续替换为真实数据库查询
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
