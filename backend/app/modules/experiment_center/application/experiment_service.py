import json
import logging
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evaluation_center.application.code_evaluators import run_all_code_evaluators
from app.modules.evaluation_center.application.evaluation_service import evaluation_service
from app.modules.evaluation_center.schemas.evaluation_schema import EvaluateRequest
from app.modules.experiment_center.domain.enums import ExperimentStatus, Winner
from app.modules.experiment_center.domain.exceptions import (
    experiment_not_found,
    invalid_version_pair,
)
from app.modules.experiment_center.infrastructure.repositories import (
    experiment_repo,
    experiment_result_repo,
)
from app.modules.experiment_center.schemas.experiment_schema import (
    CompareResponse,
    ExperimentCreate,
    ExperimentDetailResponse,
    ExperimentListResponse,
    MetricComparison,
    VersionMetricSummary,
)
from app.modules.prompt_center.application.prompt_render_service import render_prompt
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_def_repo,
    prompt_test_case_repo,
    prompt_version_repo,
)
from app.runtime.llm.client import LlmResult, llm_client

logger = logging.getLogger(__name__)


class ExperimentService:
    def create_experiment(self, db: Session, data: ExperimentCreate, operator_id: str | None = None) -> ExperimentDetailResponse:
        source_version = prompt_version_repo.get_by_id(db, data.source_version_id)
        target_version = prompt_version_repo.get_by_id(db, data.target_version_id)
        if source_version is None or target_version is None:
            raise experiment_not_found(0)
        if (
            source_version.prompt_id != target_version.prompt_id
            or source_version.prompt_id != data.prompt_id
        ):
            raise invalid_version_pair()

        record = experiment_repo.create(db, {
            "name": data.name,
            "description": data.description,
            "prompt_id": data.prompt_id,
            "source_version_id": data.source_version_id,
            "target_version_id": data.target_version_id,
            "status": ExperimentStatus.PENDING.value,
            "total_samples": len(data.test_case_ids),
            "test_case_ids": data.test_case_ids,
            "created_by": operator_id,
        })

        return self._to_detail(db, record)

    def run_experiment(self, db: Session, experiment_id: int) -> ExperimentDetailResponse:
        experiment = experiment_repo.get_by_id(db, experiment_id)
        if experiment is None:
            raise experiment_not_found(experiment_id)

        experiment_repo.update(db, experiment_id, {"status": ExperimentStatus.RUNNING.value})

        prompt = prompt_def_repo.get_by_id(db, experiment.prompt_id)
        source_version = prompt_version_repo.get_by_id(db, experiment.source_version_id)
        target_version = prompt_version_repo.get_by_id(db, experiment.target_version_id)

        try:
            errors = 0
            for result in experiment_result_repo.get_by_experiment(db, experiment_id):
                if result.status == "failed":
                    errors += 1
            if errors > 0:
                pass

            all_results: list[dict] = []
            for version_label, version_record in [("source", source_version), ("target", target_version)]:
                output = self._call_llm_for_version(db, experiment_id, version_label, version_record, prompt)
                all_results.append(output)

            comparison = self._compare_results(db, experiment_id)
            winner = comparison.get("winner", Winner.DRAW.value)
            experiment_repo.update(db, experiment_id, {
                "status": ExperimentStatus.COMPLETED.value,
                "winner_version": winner,
                "summary": {
                    "source_metrics": comparison.get("source_metrics", {}),
                    "target_metrics": comparison.get("target_metrics", {}),
                    "winner": winner,
                    "total_samples": experiment.total_samples,
                },
            })

        except Exception as e:
            logger.exception("实验运行失败: %s", experiment_id)
            experiment_repo.update(db, experiment_id, {
                "status": ExperimentStatus.FAILED.value,
                "summary": {"error": str(e)},
            })

        return self._to_detail(db, experiment_repo.get_by_id(db, experiment_id))

    def _call_llm_for_version(
        self, db: Session, experiment_id: int,
        version_label: str, version_record: Any, prompt_def: Any,
    ) -> dict:
        test_cases = prompt_test_case_repo.list_by_prompt(db, prompt_def.id)
        experiment = experiment_repo.get_by_id(db, experiment_id)
        selected_ids = set(experiment.test_case_ids or []) if experiment else set()
        if selected_ids:
            test_cases = [case for case in test_cases if case.id in selected_ids]
        if not test_cases:
            test_cases = []

        results = []
        for tc in test_cases:
            try:
                rendered = render_prompt(
                    db=db,
                    prompt_key=prompt_def.prompt_key,
                    environment="development",
                    version=version_record.version,
                    variables=tc.input_data,
                    user_question=tc.input_data.get("user_question", ""),
                )
                system_msg = ""
                user_msg = ""
                for m in rendered.messages:
                    if m["role"] == "system":
                        system_msg = m["content"]
                    elif m["role"] == "user":
                        user_msg = m["content"]

                start = perf_counter()
                llm_result: LlmResult = llm_client.chat(
                    prompt_content=system_msg or None,
                    user_message=user_msg,
                )
                latency = max(1, int((perf_counter() - start) * 1000))

                result_record = experiment_result_repo.create(db, {
                    "experiment_id": experiment_id,
                    "version": version_label,
                    "test_case_id": tc.id,
                    "version_id": version_record.id,
                    "input_data": tc.input_data,
                    "raw_output": llm_result.content,
                    "token_usage": {
                        "input_tokens": llm_result.prompt_tokens,
                        "output_tokens": llm_result.completion_tokens,
                        "total_tokens": llm_result.total_tokens,
                    },
                    "latency_ms": latency,
                    "status": "completed" if llm_result.success else "failed",
                })

                eval_results = run_all_code_evaluators(
                    output=llm_result.content,
                )
                if eval_results:
                    experiment_result_repo.update(db, result_record.id, {
                        "metrics": eval_results,
                    })

                results.append({
                    "test_case_id": tc.id,
                    "success": llm_result.success,
                    "latency": latency,
                    "tokens": llm_result.total_tokens,
                    "metrics": eval_results,
                })

            except Exception as e:
                logger.warning("实验样本执行失败: version=%s case=%s err=%s", version_label, tc.id, e)
                experiment_result_repo.create(db, {
                    "experiment_id": experiment_id,
                    "version": version_label,
                    "test_case_id": tc.id,
                    "version_id": version_record.id,
                    "input_data": tc.input_data if tc else {},
                    "raw_output": None,
                    "status": "failed",
                })

        return {"version": version_label, "results": results, "total": len(results)}

    def _compare_results(self, db: Session, experiment_id: int) -> dict[str, Any]:
        source_metrics = experiment_result_repo.get_aggregate_metrics(db, experiment_id, "source")
        target_metrics = experiment_result_repo.get_aggregate_metrics(db, experiment_id, "target")

        source_scores: dict[str, float] = {m["evaluator_key"]: m["avg_score"] for m in source_metrics}
        target_scores: dict[str, float] = {m["evaluator_key"]: m["avg_score"] for m in target_metrics}

        all_keys = set(source_scores.keys()) | set(target_scores.keys())
        source_wins = 0
        target_wins = 0
        draws = 0

        for key in all_keys:
            s = source_scores.get(key, 0)
            t = target_scores.get(key, 0)
            if s > t:
                source_wins += 1
            elif t > s:
                target_wins += 1
            else:
                draws += 1

        if source_wins > target_wins:
            winner = Winner.SOURCE.value
        elif target_wins > source_wins:
            winner = Winner.TARGET.value
        else:
            winner = Winner.DRAW.value

        source_summary = {
            m["evaluator_key"]: {"avg_score": m["avg_score"], "sample_count": m["sample_count"]}
            for m in source_metrics
        }
        target_summary = {
            m["evaluator_key"]: {"avg_score": m["avg_score"], "sample_count": m["sample_count"]}
            for m in target_metrics
        }

        source_results = experiment_result_repo.get_by_experiment_and_version(db, experiment_id, "source")
        target_results = experiment_result_repo.get_by_experiment_and_version(db, experiment_id, "target")

        def calc_avg_tokens(results: list) -> float:
            tokens = [r.token_usage.get("total_tokens", 0) for r in results if r.token_usage]
            return round(sum(tokens) / len(tokens), 2) if tokens else 0

        def calc_avg_latency(results: list) -> float:
            latencies = [r.latency_ms for r in results if r.latency_ms]
            return round(sum(latencies) / len(latencies), 2) if latencies else 0

        return {
            "winner": winner,
            "source_metrics": source_summary,
            "target_metrics": target_summary,
            "source_wins": source_wins,
            "target_wins": target_wins,
            "draws": draws,
            "source_avg_tokens": calc_avg_tokens(source_results),
            "target_avg_tokens": calc_avg_tokens(target_results),
            "source_avg_latency": calc_avg_latency(source_results),
            "target_avg_latency": calc_avg_latency(target_results),
        }

    def compare_versions(self, db: Session, experiment_id: int) -> CompareResponse:
        experiment = experiment_repo.get_by_id(db, experiment_id)
        if experiment is None:
            raise experiment_not_found(experiment_id)

        source_version = prompt_version_repo.get_by_id(db, experiment.source_version_id)
        target_version = prompt_version_repo.get_by_id(db, experiment.target_version_id)

        source_aggregate = experiment_result_repo.get_aggregate_metrics(db, experiment_id, "source")
        target_aggregate = experiment_result_repo.get_aggregate_metrics(db, experiment_id, "target")

        source_tokens = []
        target_tokens = []
        source_latency = []
        target_latency = []
        source_results = experiment_result_repo.get_by_experiment_and_version(
            db, experiment_id, "source"
        )
        target_results = experiment_result_repo.get_by_experiment_and_version(
            db, experiment_id, "target"
        )
        for r in source_results:
            if r.token_usage:
                source_tokens.append(r.token_usage.get("total_tokens", 0))
            if r.latency_ms:
                source_latency.append(r.latency_ms)
        for r in target_results:
            if r.token_usage:
                target_tokens.append(r.token_usage.get("total_tokens", 0))
            if r.latency_ms:
                target_latency.append(r.latency_ms)

        source_summary = VersionMetricSummary(
            version=source_version.version if source_version else "source",
            metrics={m["evaluator_key"]: m["avg_score"] for m in source_aggregate},
            avg_tokens=round(sum(source_tokens) / len(source_tokens), 2) if source_tokens else 0,
            avg_latency_ms=round(sum(source_latency) / len(source_latency), 2) if source_latency else 0,
            sample_count=len(source_results),
        )
        target_summary = VersionMetricSummary(
            version=target_version.version if target_version else "target",
            metrics={m["evaluator_key"]: m["avg_score"] for m in target_aggregate},
            avg_tokens=round(sum(target_tokens) / len(target_tokens), 2) if target_tokens else 0,
            avg_latency_ms=round(sum(target_latency) / len(target_latency), 2) if target_latency else 0,
            sample_count=len(target_results),
        )

        all_keys = set(source_summary.metrics.keys()) | set(target_summary.metrics.keys())
        metric_comparisons = []
        for key in sorted(all_keys):
            s = source_summary.metrics.get(key, 0)
            t = target_summary.metrics.get(key, 0)
            metric_comparisons.append(MetricComparison(
                metric_key=key,
                source_score=s,
                target_score=t,
                diff=round(t - s, 4),
                better="target" if t > s else "source" if s > t else "draw",
            ))

        return CompareResponse(
            experiment_id=experiment_id,
            experiment_name=experiment.name,
            status=experiment.status,
            winner=experiment.winner_version or "pending",
            source_version=source_summary,
            target_version=target_summary,
            metric_comparisons=metric_comparisons,
        )

    def list_experiments(self, db: Session, page: int = 1, page_size: int = 20) -> tuple[list[ExperimentListResponse], int]:
        offset = (page - 1) * page_size
        items, total = experiment_repo.list(db, offset=offset, limit=page_size)
        result = []
        for item in items:
            source = prompt_version_repo.get_by_id(db, item.source_version_id)
            target = prompt_version_repo.get_by_id(db, item.target_version_id)
            result.append(ExperimentListResponse(
                id=item.id,
                name=item.name,
                status=item.status,
                winner_version=item.winner_version,
                source_version=source.version if source else "?",
                target_version=target.version if target else "?",
                total_samples=item.total_samples,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
            ))
        return result, total

    def get_experiment(self, db: Session, experiment_id: int) -> ExperimentDetailResponse:
        experiment = experiment_repo.get_by_id(db, experiment_id)
        if experiment is None:
            raise experiment_not_found(experiment_id)
        return self._to_detail(db, experiment)

    def _to_detail(self, db: Session, experiment: Any) -> ExperimentDetailResponse:
        source = prompt_version_repo.get_by_id(db, experiment.source_version_id)
        target = prompt_version_repo.get_by_id(db, experiment.target_version_id)
        source_results = experiment_result_repo.get_by_experiment_and_version(db, experiment.id, "source")
        target_results = experiment_result_repo.get_by_experiment_and_version(db, experiment.id, "target")

        return ExperimentDetailResponse(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            prompt_id=experiment.prompt_id,
            source_version_id=experiment.source_version_id,
            target_version_id=experiment.target_version_id,
            source_version=source.version if source else "?",
            target_version=target.version if target else "?",
            status=experiment.status,
            winner_version=experiment.winner_version,
            total_samples=experiment.total_samples,
            completed_samples=sum(1 for r in source_results if r.status == "completed"),
            summary=experiment.summary,
            created_by=experiment.created_by,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )


experiment_service = ExperimentService()
