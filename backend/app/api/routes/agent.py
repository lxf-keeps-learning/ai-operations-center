from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.application.agent_service import agent_service
from app.schemas.agent import AgentTaskResponse, AnalyzeRequest, ChatRequest
from app.schemas.common import ApiResponse
from app.utils.sse import to_sse

router = APIRouter()


@router.post("/chat", response_model=ApiResponse[AgentTaskResponse], summary="AI 对话")
async def chat(payload: ChatRequest) -> ApiResponse[AgentTaskResponse]:
    task = agent_service.create_chat_task(payload)
    return ApiResponse(message="success", traceId=task.trace_id, data=task.to_response())


@router.post("/analyze", response_model=ApiResponse[AgentTaskResponse], summary="AI 分析")
async def analyze(payload: AnalyzeRequest) -> ApiResponse[AgentTaskResponse]:
    task = agent_service.create_analyze_task(payload)
    return ApiResponse(message="success", traceId=task.trace_id, data=task.to_response())


@router.get(
    "/stream",
    summary="SSE 流式输出",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "example": (
                        'event: token\n'
                        'data: {"traceId":"trace_xxx","content":"今日整体运营情况如下："}\n\n'
                    )
                }
            },
        }
    },
)
async def stream(
    trace_id: str = Query(alias="traceId", description="Trace 编号"),
    session_id: str | None = Query(default=None, alias="sessionId", description="Session 编号"),
) -> StreamingResponse:
    async def event_generator():
        async for event in agent_service.stream_events(trace_id=trace_id, session_id=session_id):
            yield to_sse(event.event, event.model_dump(exclude={"event"}, by_alias=True))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
