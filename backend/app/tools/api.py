from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.exception.error_code import NOT_FOUND
from app.core.schema.response_schema import ApiResponse
from app.tool_center.exceptions import ToolNotFoundError
from app.tool_center.contracts import BaseToolInput, ToolContext
from app.tool_center.registry import get_tool, list_tools

router = APIRouter(tags=["Tool Center"])


class ToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    context: ToolContext = Field(default_factory=ToolContext)
    filters: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class ToolDescriptor(BaseModel):
    name: str
    description: str


@router.get("/tools", response_model=ApiResponse[list[ToolDescriptor]])
def get_tools() -> ApiResponse[list[ToolDescriptor]]:
    tools = [get_tool(name) for name in sorted(list_tools())]
    return ApiResponse(
        data=[
            ToolDescriptor(name=tool.name, description=tool.description)
            for tool in tools
        ]
    )


@router.post("/tools/call", response_model=ApiResponse[dict])
def call_tool(payload: ToolCallRequest) -> ApiResponse[dict]:
    try:
        tool = get_tool(payload.tool_name)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=NOT_FOUND.http_status, detail=str(e)) from e

    # Query Tool 使用 filters；Analysis/Action Tool 可通过 params 传结构化参数。
    # 统一合并到 BaseToolInput.filters，具体 Tool 再解析自己需要的字段。
    merged_filters = {**payload.filters, **payload.params}
    inp = BaseToolInput(
        context=payload.context,
        filters=merged_filters,
    )
    result = tool.run(inp)
    return ApiResponse(data=result.model_dump())
