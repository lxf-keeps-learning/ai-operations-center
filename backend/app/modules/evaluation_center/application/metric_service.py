import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evaluation_center.domain.enums import EvaluatorType, MetricName
from app.modules.evaluation_center.infrastructure.repositories import (
    evaluation_metric_repo,
    evaluation_result_repo,
)

logger = logging.getLogger(__name__)


def calculate_metrics(db: Session, prompt_key: str) -> dict[str, Any]:
    results, total = evaluation_result_repo.list_by_prompt(db, prompt_key, limit=10000)
    if total == 0:
        return {
            "prompt_key": prompt_key,
            "total_evaluations": 0,
            "compliance_rate": 0.0,
            "format_compliance": 0.0,
            "hallucination_rate": 0.0,
            "evidence_complete_rate": 0.0,
            "avg_score": 0.0,
            "pass_rate": 0.0,
        }

    total_checks = len(results)
    passed_checks = sum(1 for r in results if r.passed)
    total_score = sum(r.score for r in results if r.score is not None)

    format_results = [r for r in results if r.evaluator_key == "json_format"]
    format_passed = sum(1 for r in format_results if r.passed) if format_results else 0

    hallucination_results = [r for r in results if r.evaluator_key == "no_hallucination"]
    hallucination_passed = sum(1 for r in hallucination_results if r.passed) if hallucination_results else 0

    evidence_results = [r for r in results if r.evaluator_key == "evidence_provided"]
    evidence_passed = sum(1 for r in evidence_results if r.passed) if evidence_results else 0

    metrics = {
        MetricName.TOTAL_EVALUATIONS.value: float(total_checks),
        MetricName.COMPLIANCE_RATE.value: round(passed_checks / total_checks * 100, 2) if total_checks > 0 else 0.0,
        MetricName.PASS_RATE.value: round(passed_checks / total_checks * 100, 2) if total_checks > 0 else 0.0,
        MetricName.AVG_SCORE.value: round(total_score / total_checks, 4) if total_checks > 0 else 0.0,
        MetricName.FORMAT_COMPLIANCE.value: round(format_passed / len(format_results) * 100, 2) if format_results else 0.0,
        MetricName.HALLUCINATION_RATE.value: round((len(hallucination_results) - hallucination_passed) / len(hallucination_results) * 100, 2) if hallucination_results else 0.0,
        MetricName.EVIDENCE_COMPLETE_RATE.value: round(evidence_passed / len(evidence_results) * 100, 2) if evidence_results else 0.0,
    }

    _persist_metrics(db, prompt_key, metrics, total_checks)

    metrics["prompt_key"] = prompt_key
    metrics["total_evaluations"] = total_checks
    return metrics


def _persist_metrics(db: Session, prompt_key: str, metrics: dict, sample_count: int) -> None:
    for metric_name, metric_value in metrics.items():
        if metric_name == "prompt_key" or metric_name == "total_evaluations":
            continue
        try:
            evaluation_metric_repo.upsert(db, {
                "prompt_key": prompt_key,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "sample_count": sample_count,
            })
        except Exception as e:
            logger.warning("持久化指标 %s 失败: %s", metric_name, e)


def get_metrics_summary(db: Session, prompt_key: str) -> dict[str, Any]:
    metric_records = evaluation_metric_repo.get_by_prompt(db, prompt_key)
    result = {"prompt_key": prompt_key}
    for record in metric_records:
        result[record.metric_name] = record.metric_value
    return result
