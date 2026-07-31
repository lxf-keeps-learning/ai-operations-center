import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.enums import EvaluatorType
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_evaluation_repo,
    prompt_test_run_repo,
)
from app.modules.prompt_center.schemas.test_schema import EvaluationResponse, EvaluationSummary

logger = logging.getLogger(__name__)


def run_deterministic_evaluations(
    db: Session, test_run_id: int,
) -> list[EvaluationResponse]:
    run_record = prompt_test_run_repo.get_by_id(db, test_run_id)
    if run_record is None:
        return []

    output = run_record.raw_output or ""
    structured = run_record.structured_output
    input_data = run_record.input_data

    evaluations: list[dict] = []

    json_valid, json_error = _check_json_valid(output, structured)
    evaluations.append({
        "test_run_id": test_run_id,
        "evaluator_key": "json_format",
        "evaluator_type": EvaluatorType.DETERMINISTIC.value,
        "score": 1.0 if json_valid else 0.0,
        "passed": json_valid,
        "reason": json_error or "JSON 格式通过",
        "violations": [json_error] if json_error else [],
    })

    if structured:
        required_fields = ["title", "priority"]
        missing = [f for f in required_fields if f not in structured]
        has_required = len(missing) == 0
        if not has_required and isinstance(structured, dict):
            pass

        for check in _get_field_checks(test_run_id, structured, input_data):
            evaluations.append(check)

    records = prompt_evaluation_repo.batch_create(db, evaluations)
    return [EvaluationResponse.model_validate(r) for r in records]


def run_llm_evaluations(
    db: Session, test_run_id: int,
) -> list[EvaluationResponse]:
    run_record = prompt_test_run_repo.get_by_id(db, test_run_id)
    if run_record is None:
        return []
    return []


def get_evaluation_summary(db: Session, test_run_id: int) -> EvaluationSummary:
    evaluations = prompt_evaluation_repo.get_by_test_run(db, test_run_id)
    total = len(evaluations)
    passed = sum(1 for e in evaluations if e.passed)
    return EvaluationSummary(
        total_checks=total,
        passed_checks=passed,
        compliance_rate=round(passed / total * 100, 2) if total > 0 else 0.0,
        evaluations=[EvaluationResponse.model_validate(e) for e in evaluations],
    )


def get_compliance_stats(db: Session, prompt_id: int) -> dict[str, Any]:
    return prompt_evaluation_repo.get_compliance_stats(db, prompt_id)


def _check_json_valid(output: str, structured: dict | None) -> tuple[bool, str | None]:
    if structured is not None:
        return True, None
    if not output.strip():
        return False, "模型输出为空"
    cleaned = output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
    try:
        json.loads(cleaned)
        return True, None
    except json.JSONDecodeError as e:
        return False, f"JSON 解析失败: {e.msg}"


def _get_field_checks(test_run_id: int, structured: dict, input_data: dict) -> list[dict]:
    checks: list[dict] = []

    if isinstance(structured, dict):
        priority = structured.get("priority", "")
        valid_priorities = {"P0", "P1", "P2", "P3", "critical", "high", "medium", "low"}
        priority_valid = priority in valid_priorities
        checks.append({
            "test_run_id": test_run_id,
            "evaluator_key": "risk_level_compliance",
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 1.0 if priority_valid else 0.0,
            "passed": priority_valid,
            "reason": "风险等级符合要求" if priority_valid else f"风险等级 '{priority}' 不在允许范围内",
            "violations": [] if priority_valid else [f"非法风险等级: {priority}"],
        })

        title = structured.get("title", "").strip()
        has_title = len(title) > 0
        checks.append({
            "test_run_id": test_run_id,
            "evaluator_key": "has_title",
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 1.0 if has_title else 0.0,
            "passed": has_title,
            "reason": "包含标题" if has_title else "缺少标题字段",
            "violations": [] if has_title else ["title 为空"],
        })

    return checks
