from pydantic import Field

from app.schemas.common import IocBaseModel


class EvaluationResultEntity(IocBaseModel):
    trace_id: str
    prompt_key: str
    prompt_version: str
    graph_name: str
    node_name: str
    evaluator_key: str
    evaluator_type: str
    score: float
    passed: bool
    reason: str | None = None
    violations: list | None = None


class EvaluationMetricEntity(IocBaseModel):
    prompt_key: str
    prompt_version_id: int | None = None
    metric_name: str
    metric_value: float
    sample_count: int = 0
