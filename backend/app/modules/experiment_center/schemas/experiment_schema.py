from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class ExperimentCreate(IocBaseModel):
    name: str = Field(description="实验名称")
    description: str | None = None
    prompt_id: int = Field(description="Prompt ID")
    source_version_id: int = Field(description="源版本 ID")
    target_version_id: int = Field(description="目标版本 ID")
    test_case_ids: list[int] = Field(default_factory=list, description="测试用例 ID 列表")


class ExperimentListResponse(IocBaseModel):
    id: int
    name: str
    status: str
    winner_version: str | None = None
    source_version: str = ""
    target_version: str = ""
    total_samples: int = 0
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ExperimentDetailResponse(IocBaseModel):
    id: int
    name: str
    description: str | None = None
    prompt_id: int
    source_version_id: int
    target_version_id: int
    source_version: str = ""
    target_version: str = ""
    status: str
    winner_version: str | None = None
    total_samples: int = 0
    completed_samples: int = 0
    summary: dict | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class VersionMetricSummary(IocBaseModel):
    version: str
    metrics: dict[str, float] = Field(default_factory=dict)
    avg_tokens: float = 0
    avg_latency_ms: float = 0
    sample_count: int = 0


class MetricComparison(IocBaseModel):
    metric_key: str
    source_score: float = 0
    target_score: float = 0
    diff: float = 0
    better: str = "draw"


class CompareResponse(IocBaseModel):
    experiment_id: int
    experiment_name: str
    status: str
    winner: str = "pending"
    source_version: VersionMetricSummary
    target_version: VersionMetricSummary
    metric_comparisons: list[MetricComparison] = Field(default_factory=list)


class ExperimentRunResult(IocBaseModel):
    experiment_id: int
    status: str
    message: str = ""


class ExperimentResultRow(IocBaseModel):
    id: int
    version: str
    test_case_id: int | None = None
    raw_output: str | None = None
    token_usage: dict | None = None
    latency_ms: float | None = None
    metrics: list | None = None
    status: str
    created_at: datetime
