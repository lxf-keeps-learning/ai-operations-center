from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.trace.trace_context import get_trace_id
from app.utils.ids import new_trace_id

T = TypeVar("T")


def _default_trace_id() -> str:
    return get_trace_id() or new_trace_id()


class IocBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ApiResponse(IocBaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    trace_id: str = Field(default_factory=_default_trace_id, alias="traceId")
    data: T | None = None

    @computed_field
    @property
    def success(self) -> bool:
        return self.code == 0


class PageContext(IocBaseModel):
    page: str = "operation_center"
    filters: dict[str, object] = Field(default_factory=dict)
    selected: dict[str, object] = Field(default_factory=dict)


class BusinessContext(IocBaseModel):
    object_type: str = "operation_dashboard"
    object_id: str | None = None
    refs: dict[str, object] = Field(default_factory=dict)


class PaginatedResult(IocBaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
