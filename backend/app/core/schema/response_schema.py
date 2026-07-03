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
        return self.code == 0


def success_response(*, data: T | None = None, message: str = "success", trace_id: str | None = None) -> ApiResponse[T]:
    return ApiResponse(
        code=0,
        message=message,
        trace_id=trace_id or _default_trace_id(),
        data=data,
    )


def error_response(*, code: int, message: str, trace_id: str | None = None) -> ApiResponse[None]:
    return ApiResponse(
        code=code,
        message=message,
        trace_id=trace_id or _default_trace_id(),
        data=None,
    )
