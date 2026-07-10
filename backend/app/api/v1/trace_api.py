"""
Trace 链路查询接口 — GET /traces/{trace_id}

根据 traceId 查询一次请求的完整调用链（Span 列表）。
每个 Span 包含 spanId、parentSpanId、operation、时间、状态等信息。

现状：
  Sprint1 阶段使用 Mock 数据展示 Trace 链路结构，
  包括 request → api → service → llm → response 的典型链路。
  后续接入真实链路追踪后替换为数据库查询。
"""

from fastapi import APIRouter

from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.get("/traces/{trace_id}", summary="Trace 链路查询")
async def get_trace(trace_id: str) -> ApiResponse[dict]:
    return ApiResponse(
        data={
            "traceId": trace_id,
            "spans": [
                {
                    "spanId": "span_001",
                    "parentSpanId": "",
                    "operation": "request received",
                    "startTime": "2026-07-03T10:00:00.000",
                    "endTime": "2026-07-03T10:00:00.010",
                    "status": "OK",
                    "service": "fastapi",
                },
                {
                    "spanId": "span_002",
                    "parentSpanId": "span_001",
                    "operation": "api handled",
                    "startTime": "2026-07-03T10:00:00.010",
                    "endTime": "2026-07-03T10:00:00.020",
                    "status": "OK",
                    "service": "api",
                },
                {
                    "spanId": "span_003",
                    "parentSpanId": "span_002",
                    "operation": "service handled",
                    "startTime": "2026-07-03T10:00:00.020",
                    "endTime": "2026-07-03T10:00:00.050",
                    "status": "OK",
                    "service": "service",
                },
                {
                    "spanId": "span_004",
                    "parentSpanId": "span_003",
                    "operation": "llm called",
                    "startTime": "2026-07-03T10:00:00.050",
                    "endTime": "2026-07-03T10:00:02.350",
                    "status": "OK",
                    "service": "llm",
                    "metadata": {
                        "provider": "qwen",
                        "model": "qwen-plus",
                        "inputTokens": 1200,
                        "outputTokens": 800,
                    },
                },
                {
                    "spanId": "span_005",
                    "parentSpanId": "span_001",
                    "operation": "response returned",
                    "startTime": "2026-07-03T10:00:02.350",
                    "endTime": "2026-07-03T10:00:02.360",
                    "status": "OK",
                    "service": "fastapi",
                },
            ],
        }
    )
