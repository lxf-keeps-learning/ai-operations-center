from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class IocBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ApiResponse(IocBaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    trace_id: str = Field(alias="traceId")
    data: T | None = None


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
