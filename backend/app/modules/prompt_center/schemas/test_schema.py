from datetime import datetime

from pydantic import Field

from app.schemas.common import IocBaseModel


class TestCaseCreate(IocBaseModel):
    case_name: str = Field(description="测试用例名称")
    case_type: str = "manual"
    input_data: dict = Field(description="测试输入数据")
    expected_output: str | None = None
    source_trace_id: str | None = None


class TestCaseResponse(IocBaseModel):
    id: int
    prompt_id: int
    case_name: str
    case_type: str
    input_data: dict
    expected_output: str | None = None
    source_trace_id: str | None = None
    enabled: bool
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class TestRunRequest(IocBaseModel):
    input_data: dict = Field(description="测试输入数据，包含 user_question 和变量值")
    test_case_id: int | None = None
    model_name: str | None = None
    provider_name: str | None = None


class DatasetTestRequest(IocBaseModel):
    test_case_ids: list[int] = Field(description="测试用例 ID 列表")
    model_name: str | None = None


class TestRunResponse(IocBaseModel):
    id: int
    prompt_id: int
    version_id: int
    test_case_id: int | None = None
    model_name: str | None = None
    input_data: dict
    rendered_prompt: str | None = None
    raw_output: str | None = None
    structured_output: dict | None = None
    token_usage: dict | None = None
    latency: float | None = None
    trace_id: str | None = None
    status: str
    evaluations: list["EvaluationResponse"] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime


class EvaluationResponse(IocBaseModel):
    id: int
    test_run_id: int
    evaluator_key: str
    evaluator_type: str
    score: float | None = None
    passed: bool
    reason: str | None = None
    violations: list | None = None
    created_at: datetime


class EvaluationSummary(IocBaseModel):
    total_checks: int = 0
    passed_checks: int = 0
    compliance_rate: float = 0.0
    evaluations: list[EvaluationResponse] = Field(default_factory=list)
