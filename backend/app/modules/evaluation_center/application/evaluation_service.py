import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evaluation_center.application.code_evaluators import run_all_code_evaluators
from app.modules.evaluation_center.application.llm_judges import run_all_llm_judges
from app.modules.evaluation_center.application.metric_service import calculate_metrics
from app.modules.evaluation_center.infrastructure.repositories import (
    evaluation_result_repo,
)
from app.modules.evaluation_center.schemas.evaluation_schema import (
    EvaluateRequest,
    EvaluationResultResponse,
)
from app.utils.ids import new_trace_id
from app.utils.timezone import now_local

logger = logging.getLogger(__name__)


class EvaluationService:
    def evaluate(
        self,
        db: Session,
        request: EvaluateRequest,
    ) -> list[EvaluationResultResponse]:
        output = request.output or ""
        input_text = request.input or ""

        code_results = run_all_code_evaluators(
            output=output,
            schema=request.schema_,
            required_fields=request.required_fields,
            field_enum_map=request.field_enum_map,
        )

        all_results: list[dict] = []
        for r in code_results:
            all_results.append({
                "trace_id": request.trace_id or new_trace_id(),
                "prompt_key": request.prompt_key,
                "prompt_version": request.prompt_version or "",
                "graph_name": request.graph_name or "",
                "node_name": request.node_name or "",
                "evaluator_key": r["evaluator_key"],
                "evaluator_type": r["evaluator_type"],
                "score": r["score"],
                "passed": r["passed"],
                "reason": r.get("reason", ""),
                "violations": r.get("violations", []),
            })

        llm_results = run_all_llm_judges(
            input_text=input_text,
            output_text=output,
        )
        for r in llm_results:
            all_results.append({
                "trace_id": request.trace_id or new_trace_id(),
                "prompt_key": request.prompt_key,
                "prompt_version": request.prompt_version or "",
                "graph_name": request.graph_name or "",
                "node_name": request.node_name or "",
                "evaluator_key": r["evaluator_key"],
                "evaluator_type": r["evaluator_type"],
                "score": r["score"],
                "passed": r["passed"],
                "reason": r.get("reason", ""),
                "violations": r.get("violations", []),
            })

        records = evaluation_result_repo.batch_create(db, all_results)

        if request.prompt_key:
            try:
                calculate_metrics(db, request.prompt_key)
            except Exception as e:
                logger.warning("指标计算失败: %s", e)

        return [EvaluationResultResponse.model_validate(r) for r in records]

    def evaluate_trace_background(
        self,
        db: Session,
        trace_id: str,
        prompt_key: str,
        prompt_version: str,
        graph_name: str,
        node_name: str,
        input_text: str,
        output: str,
        schema: dict | None = None,
        required_fields: list[str] | None = None,
        field_enum_map: dict[str, set] | None = None,
    ) -> None:
        req = EvaluateRequest(
            trace_id=trace_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            graph_name=graph_name,
            node_name=node_name,
            input=input_text,
            output=output,
            schema_=schema,
            required_fields=required_fields,
            field_enum_map=field_enum_map,
        )
        try:
            self.evaluate(db, req)
            logger.info("后台评估完成: trace_id=%s, prompt_key=%s", trace_id, prompt_key)
        except Exception as e:
            logger.exception("后台评估失败: trace_id=%s", trace_id)

    def get_results_by_trace(self, db: Session, trace_id: str) -> list[EvaluationResultResponse]:
        records = evaluation_result_repo.get_by_trace(db, trace_id)
        return [EvaluationResultResponse.model_validate(r) for r in records]

    def get_results_by_prompt(
        self, db: Session, prompt_key: str, *,
        evaluator_key: str | None = None,
        passed: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvaluationResultResponse], int]:
        offset = (page - 1) * page_size
        items, total = evaluation_result_repo.list_by_prompt(
            db, prompt_key,
            evaluator_key=evaluator_key,
            passed=passed,
            offset=offset,
            limit=page_size,
        )
        return [EvaluationResultResponse.model_validate(r) for r in items], total


evaluation_service = EvaluationService()
