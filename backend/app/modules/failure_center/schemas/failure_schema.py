from datetime import datetime

from pydantic import Field

from app.modules.evaluation_center.schemas.evaluation_schema import EvaluationResultResponse
from app.schemas.common import IocBaseModel


class CollectRequest(IocBaseModel):
    prompt_key: str | None = None
    eval_result_ids: list[int] | None = None
    auto_convert: bool = False


class FailureListResponse(IocBaseModel):
    id: int
    trace_id: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    failure_type: str
    severity: str
    reason: str | None = None
    status: str
    eval_score: float | None = None
    created_at: datetime
    updated_at: datetime


class FailureDetailResponse(IocBaseModel):
    id: int
    trace_id: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    failure_type: str
    severity: str
    input: str | None = None
    output: str | None = None
    reason: str | None = None
    analysis: str | None = None
    status: str
    eval_result_ids: list | None = None
    generated_case_id: int | None = None
    eval_score: float | None = None
    eval_results: list[EvaluationResultResponse] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class FailureStatsResponse(IocBaseModel):
    total: int = 0
    by_type: dict = Field(default_factory=dict)
    by_severity: dict = Field(default_factory=dict)
    by_status: dict = Field(default_factory=dict)


class AnalyzeRequest(IocBaseModel):
    analysis: str = Field(description="分析内容")


class StatusUpdate(IocBaseModel):
    status: str = Field(description="新状态")
