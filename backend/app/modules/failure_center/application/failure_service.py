import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evaluation_center.domain.enums import EvaluatorKey
from app.modules.evaluation_center.infrastructure.repositories import evaluation_result_repo
from app.modules.failure_center.domain.enums import FAILURE_TYPE_MAP, FailureSeverity, FailureStatus, FailureType
from app.modules.failure_center.domain.exceptions import failure_not_found
from app.modules.failure_center.infrastructure.repositories import failure_case_repo
from app.modules.failure_center.schemas.failure_schema import (
    CollectRequest,
    FailureDetailResponse,
    FailureListResponse,
    FailureStatsResponse,
)
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_def_repo,
    prompt_test_case_repo,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = [FailureSeverity.CRITICAL, FailureSeverity.HIGH, FailureSeverity.MEDIUM, FailureSeverity.LOW]


class FailureService:
    def collect_from_evaluation(self, db: Session, data: CollectRequest) -> list[FailureDetailResponse]:
        if data.eval_result_ids:
            eval_results = []
            for rid in data.eval_result_ids:
                r = evaluation_result_repo.get_by_id(db, rid)
                if r:
                    eval_results.append(r)
        elif data.prompt_key:
            results, _ = evaluation_result_repo.list_by_prompt(
                db, data.prompt_key, passed=False, limit=100,
            )
            eval_results = results
        else:
            return []

        created: list = []
        for er in eval_results:
            if failure_case_repo.exists_by_trace_and_type(db, er.trace_id, er.evaluator_key):
                continue
            ftype = FAILURE_TYPE_MAP.get(er.evaluator_key, FailureType.UNKNOWN).value
            severity = self._calculate_severity(er.evaluator_key, er.score)
            record = failure_case_repo.create(db, {
                "trace_id": er.trace_id,
                "prompt_key": er.prompt_key,
                "prompt_version": er.prompt_version,
                "graph_name": er.graph_name,
                "node_name": er.node_name,
                "failure_type": ftype,
                "severity": severity.value,
                "input": er.reason or "",
                "output": "",
                "reason": er.reason or "",
                "status": FailureStatus.PENDING.value,
                "eval_result_ids": [er.id],
                "eval_score": er.score,
            })
            created.append(self._to_detail(db, record))

        return created

    def convert_to_case(self, db: Session, failure_id: int) -> FailureDetailResponse:
        record = failure_case_repo.get_by_id(db, failure_id)
        if record is None:
            raise failure_not_found(failure_id)

        prompt = prompt_def_repo.get_by_key(db, record.prompt_key) if record.prompt_key else None
        if not prompt:
            raise failure_not_found(failure_id)

        input_data: dict = {"user_question": record.input or ""}
        if record.trace_id:
            input_data["source_trace_id"] = record.trace_id

        test_case = prompt_test_case_repo.create(db, {
            "prompt_id": prompt.id,
            "case_name": f"失败案例: {record.failure_type} - {record.trace_id or 'unknown'}",
            "case_type": "failure",
            "input_data": input_data,
            "expected_output": "",
            "source_trace_id": record.trace_id,
            "created_by": "failure_center",
        })

        failure_case_repo.update(db, failure_id, {
            "status": FailureStatus.CONVERTED.value,
            "generated_case_id": test_case.id,
        })

        return self._to_detail(db, failure_case_repo.get_by_id(db, failure_id))

    def analyze_failure(self, db: Session, failure_id: int, analysis: str) -> FailureDetailResponse:
        record = failure_case_repo.get_by_id(db, failure_id)
        if record is None:
            raise failure_not_found(failure_id)
        failure_case_repo.update(db, failure_id, {
            "analysis": analysis,
            "status": FailureStatus.ANALYZED.value,
        })
        return self._to_detail(db, failure_case_repo.get_by_id(db, failure_id))

    def update_status(self, db: Session, failure_id: int, status: str) -> FailureDetailResponse:
        record = failure_case_repo.get_by_id(db, failure_id)
        if record is None:
            raise failure_not_found(failure_id)
        failure_case_repo.update(db, failure_id, {"status": status})
        return self._to_detail(db, failure_case_repo.get_by_id(db, failure_id))

    def list_failures(
        self, db: Session, *,
        prompt_key: str | None = None,
        failure_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FailureListResponse], int]:
        offset = (page - 1) * page_size
        items, total = failure_case_repo.list(
            db, prompt_key=prompt_key, failure_type=failure_type,
            status=status, severity=severity, offset=offset, limit=page_size,
        )
        return [FailureListResponse(
            id=r.id, trace_id=r.trace_id, prompt_key=r.prompt_key,
            prompt_version=r.prompt_version, failure_type=r.failure_type,
            severity=r.severity, reason=r.reason[:200] if r.reason else None,
            status=r.status, eval_score=r.eval_score,
            created_at=r.created_at, updated_at=r.updated_at,
        ) for r in items], total

    def get_failure(self, db: Session, failure_id: int) -> FailureDetailResponse:
        record = failure_case_repo.get_by_id(db, failure_id)
        if record is None:
            raise failure_not_found(failure_id)
        return self._to_detail(db, record)

    def get_stats(self, db: Session, prompt_key: str) -> FailureStatsResponse:
        stats = failure_case_repo.get_failure_stats(db, prompt_key)
        return FailureStatsResponse(**stats)

    def auto_collect(self, db: Session, prompt_key: str) -> list[FailureDetailResponse]:
        req = CollectRequest(prompt_key=prompt_key)
        return self.collect_from_evaluation(db, req)

    def _calculate_severity(self, evaluator_key: str, score: float | None) -> FailureSeverity:
        if score is None:
            return FailureSeverity.MEDIUM
        if evaluator_key in ("json_format", "no_hallucination", "schema_compliance"):
            if score < 0.3:
                return FailureSeverity.CRITICAL
            if score < 0.6:
                return FailureSeverity.HIGH
        if score < 0.3:
            return FailureSeverity.HIGH
        if score < 0.6:
            return FailureSeverity.MEDIUM
        return FailureSeverity.LOW

    def _to_detail(self, db: Session, record: Any) -> FailureDetailResponse:
        eval_results = []
        if record.eval_result_ids:
            for rid in record.eval_result_ids:
                r = evaluation_result_repo.get_by_id(db, rid)
                if r:
                    from app.modules.evaluation_center.schemas.evaluation_schema import EvaluationResultResponse
                    eval_results.append(EvaluationResultResponse.model_validate(r))

        return FailureDetailResponse(
            id=record.id, trace_id=record.trace_id,
            prompt_key=record.prompt_key, prompt_version=record.prompt_version,
            graph_name=record.graph_name, node_name=record.node_name,
            failure_type=record.failure_type, severity=record.severity,
            input=record.input, output=record.output, reason=record.reason,
            analysis=record.analysis, status=record.status,
            eval_result_ids=record.eval_result_ids,
            generated_case_id=record.generated_case_id,
            eval_score=record.eval_score,
            eval_results=eval_results,
            created_by=record.created_by,
            created_at=record.created_at, updated_at=record.updated_at,
        )


failure_service = FailureService()
