"""
Operation API — 运营分析 HTTP 接口。

路由：
  POST /api/v1/operation/analyze       同步分析
  POST /api/v1/operation/analyze/stream  SSE 流式分析

职责：
1. 接收前端传入的 OperationAnalyzeRequest。
2. 调用 OperationService.analyze_operation()（同步）或 stream 版本。
3. 将 OperationState 转换为 OperationAnalyzeResponse 返回。

API 层不包含任何业务分析逻辑、不直接调用 LLM、不直接查询数据库。
"""
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.analysis_stream.event_emitter import SseEventEmitter
from app.core.context.context_holder import get_request_context, get_user_context
from app.core.schema.response_schema import ApiResponse
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.schemas.response import OperationAnalyzeResponse
from app.operation_agent.service import analyze_operation
from app.operation_agent.stream_service import stream_operation_analysis
from app.utils.ids import new_trace_id

logger = logging.getLogger(__name__)
router = APIRouter()


def _current_user_context() -> dict:
    context = get_user_context()
    return {
        "user_id": context.user_id,
        "user_name": context.username,
        "tenant_id": context.org_id,
        "roles": list(context.roles),
        "permissions": list(context.permissions),
    }


@router.post("/operation/analyze", response_model=ApiResponse[OperationAnalyzeResponse])
def operation_analyze(payload: OperationAnalyzeRequest) -> ApiResponse[OperationAnalyzeResponse]:
    """
    执行运营分析并返回结果。

    请求体：
        trigger_type:   触发类型（默认 tab_analysis）
        domain:         分析领域（默认 safety，本质安全）
        active_tab:     当前活跃 Tab
        time_dimension: 时间维度（day / week / month）
        date:           分析日期

    返回（统一 ApiResponse 包裹）：
        trace_id        请求追踪 ID
        status          success / partial / failed
        summary         Markdown 格式的运营分析结论
        abnormal_items  异常项列表
        advice_items    改进建议列表
        evidence        数据来源证据
        errors          处理过程中的错误
    """
    result = analyze_operation(
        payload,
        user_context=_current_user_context(),
        trace_id=get_request_context().trace_id,
    )

    abnormal = result.get("abnormal_items", [])
    risk = result.get("risk_items", [])
    advice = result.get("advice_items", [])
    evidence = result.get("evidence", [])
    errors = result.get("errors", [])
    final_answer = result.get("final_answer", "")

    status = "failed" if errors and not final_answer else "partial" if errors else "success"

    data = OperationAnalyzeResponse(
        record_id=result.get("record_id"),
        trace_id=result.get("trace_id", ""),
        status=status,
        summary=final_answer,
        abnormal_items=abnormal,
        risk_items=risk,
        advice_items=advice,
        evidence=evidence,
        errors=errors,
    )

    return ApiResponse(data=data)


@router.post("/operation/analyze/stream")
async def operation_analyze_stream(payload: OperationAnalyzeRequest):
    """
    流式执行运营分析，SSE 实时推送节点事件。

    请求体与同步接口一致。
    返回 text/event-stream，每个事件包含 run_id、event_type、node_key、status、message。
    最终事件为 report_completed，payload 中包含完整报告数据。
    """
    run_id = get_request_context().trace_id or new_trace_id()
    user_context = _current_user_context()

    async def event_generator() -> AsyncGenerator[str, None]:
        # 同步分析无请求上下文时生成新 ID，保证 SSE run_id 不空
        emitter = SseEventEmitter(run_id=run_id)

        try:
            async for event in stream_operation_analysis(
                payload,
                emitter,
                user_context=user_context,
            ):
                yield event

        except Exception as e:
            logger.exception("SSE 流式分析异常")
            yield emitter.emit_analysis_failed(
                message="分析任务执行失败",
                error_code="ANALYSIS_STREAM_FAILED",
                error_message=str(e),
            )
            yield emitter.emit_stream_closed()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
