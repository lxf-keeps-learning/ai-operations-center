"""
统一响应模型 — 所有 API 接口必须返回此格式

成功响应：
  { code: 0, message: "success", traceId: "xxx", success: true, data: {...} }

失败响应：
  { code: 400001, message: "参数错误", traceId: "xxx", success: false, data: null }

字段说明：
  code      业务状态码（0 成功，非 0 失败）
  message   响应信息
  traceId   全链路追踪 ID
  success   是否成功（由 code == 0 自动推导）
  data      业务数据
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.trace.trace_context import get_trace_id
from app.utils.ids import new_trace_id

T = TypeVar("T")


def _default_trace_id() -> str:
    tid = get_trace_id()
    if tid:
        return tid
    return new_trace_id()


class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    code: int = 0
    message: str = "success"
    trace_id: str = Field(default_factory=_default_trace_id, alias="traceId")
    data: T | None = None

    @computed_field
    @property
    def success(self) -> bool:
        """是否成功（code == 0 即为成功）"""
        return self.code == 0


def success_response(*, data: T | None = None, message: str = "success", trace_id: str | None = None) -> ApiResponse[T]:
    """快速构造成功响应，自动注入 traceId"""
    return ApiResponse(
        code=0,
        message=message,
        trace_id=trace_id or _default_trace_id(),
        data=data,
    )


def error_response(*, code: int, message: str, trace_id: str | None = None) -> ApiResponse[None]:
    """快速构造失败响应，自动注入 traceId"""
    return ApiResponse(
        code=code,
        message=message,
        trace_id=trace_id or _default_trace_id(),
        data=None,
    )
