from app.schemas.common import IocBaseModel


class ExperimentCreateEntity(IocBaseModel):
    name: str
    description: str | None = None
    prompt_id: int
    source_version_id: int
    target_version_id: int
    test_case_ids: list[int]


class ExperimentEntity(IocBaseModel):
    name: str
    description: str | None = None
    prompt_id: int
    source_version_id: int
    target_version_id: int
    dataset_id: int | None = None
    status: str = "pending"
    winner_version: str | None = None
    total_samples: int = 0
    summary: dict | None = None


class ExperimentResultEntity(IocBaseModel):
    experiment_id: int
    version: str
    test_case_id: int | None = None
    version_id: int
    input_data: dict
    raw_output: str | None = None
    token_usage: dict | None = None
    latency_ms: float | None = None
    metrics: list[dict] | None = None
    status: str = "pending"
