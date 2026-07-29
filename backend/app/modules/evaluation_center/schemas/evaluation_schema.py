from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class EvaluateRequest(IocBaseModel):
    trace_id: str | None = None
    prompt_key: str = Field(description="Prompt Key")
    prompt_version: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    input: str = Field(default="", description="用户输入/问题")
    output: str = Field(description="模型输出")
    schema_: dict | None = Field(default=None, alias="schema", description="JSON Schema")
    required_fields: list[str] | None = None
    field_enum_map: dict[str, set[str]] | None = None


class EvaluationResultResponse(IocBaseModel):
    id: int
    trace_id: str
    prompt_key: str | None = None
    prompt_version: str | None = None
    graph_name: str | None = None
    node_name: str | None = None
    evaluator_key: str
    evaluator_type: str
    score: float | None = None
    passed: bool
    reason: str | None = None
    violations: list | None = None
    created_at: datetime


class EvaluationMetricsResponse(IocBaseModel):
    prompt_key: str
    total_evaluations: int = 0
    compliance_rate: float = 0.0
    format_compliance: float = 0.0
    hallucination_rate: float = 0.0
    evidence_complete_rate: float = 0.0
    avg_score: float = 0.0
    pass_rate: float = 0.0


class TrendItem(IocBaseModel):
    date: str
    evaluator_key: str
    avg_score: float
    count: int


class FailureItem(IocBaseModel):
    evaluator_key: str
    failure_count: int


class EvaluatorInfo(IocBaseModel):
    key: str
    name: str
    type: str
    description: str
