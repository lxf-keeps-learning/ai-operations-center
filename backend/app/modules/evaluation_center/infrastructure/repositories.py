from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.evaluation_center.infrastructure.models import EvaluationMetric, EvaluationResult
from app.utils.timezone import now_local


class EvaluationResultRepo:
    def get_by_id(self, db: Session, result_id: int) -> EvaluationResult | None:
        return db.get(EvaluationResult, result_id)

    def get_by_trace(self, db: Session, trace_id: str) -> list[EvaluationResult]:
        stmt = (
            select(EvaluationResult)
            .where(EvaluationResult.trace_id == trace_id)
            .order_by(EvaluationResult.created_at)
        )
        return list(db.scalars(stmt).all())

    def list_by_prompt(
        self, db: Session, prompt_key: str, *,
        evaluator_key: str | None = None,
        passed: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[EvaluationResult], int]:
        stmt = select(EvaluationResult).where(EvaluationResult.prompt_key == prompt_key)
        if evaluator_key:
            stmt = stmt.where(EvaluationResult.evaluator_key == evaluator_key)
        if passed is not None:
            stmt = stmt.where(EvaluationResult.passed == passed)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        stmt = stmt.order_by(EvaluationResult.created_at.desc()).offset(offset).limit(limit)
        items = list(db.scalars(stmt).all())
        return items, total

    def create(self, db: Session, data: dict) -> EvaluationResult:
        record = EvaluationResult(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def batch_create(self, db: Session, items: list[dict]) -> list[EvaluationResult]:
        records = [EvaluationResult(**item) for item in items]
        for r in records:
            db.add(r)
        db.commit()
        for r in records:
            db.refresh(r)
        return records

    def get_recent_trend(
        self, db: Session, prompt_key: str, days: int = 7,
    ) -> list[dict[str, Any]]:
        cutoff = now_local() - timedelta(days=days)
        stmt = (
            select(
                func.date(EvaluationResult.created_at).label("date"),
                EvaluationResult.evaluator_key,
                func.avg(EvaluationResult.score).label("avg_score"),
                func.count(EvaluationResult.id).label("count"),
            )
            .where(
                EvaluationResult.prompt_key == prompt_key,
                EvaluationResult.created_at >= cutoff,
            )
            .group_by(func.date(EvaluationResult.created_at), EvaluationResult.evaluator_key)
            .order_by(func.date(EvaluationResult.created_at))
        )
        rows = db.execute(stmt).all()
        return [
            {"date": str(r[0]), "evaluator_key": r[1], "avg_score": float(r[2]) if r[2] else 0.0, "count": r[3]}
            for r in rows
        ]

    def get_failure_distribution(
        self, db: Session, prompt_key: str, days: int = 7,
    ) -> list[dict[str, Any]]:
        cutoff = now_local() - timedelta(days=days)
        stmt = (
            select(
                EvaluationResult.evaluator_key,
                func.count(EvaluationResult.id).label("failure_count"),
            )
            .where(
                EvaluationResult.prompt_key == prompt_key,
                EvaluationResult.passed == False,
                EvaluationResult.created_at >= cutoff,
            )
            .group_by(EvaluationResult.evaluator_key)
            .order_by(func.count(EvaluationResult.id).desc())
        )
        rows = db.execute(stmt).all()
        return [{"evaluator_key": r[0], "failure_count": r[1]} for r in rows]


class EvaluationMetricRepo:
    def get_by_prompt(self, db: Session, prompt_key: str) -> list[EvaluationMetric]:
        stmt = (
            select(EvaluationMetric)
            .where(EvaluationMetric.prompt_key == prompt_key)
            .order_by(EvaluationMetric.metric_name)
        )
        return list(db.scalars(stmt).all())

    def upsert(self, db: Session, data: dict) -> EvaluationMetric:
        prompt_key = data["prompt_key"]
        metric_name = data["metric_name"]
        stmt = select(EvaluationMetric).where(
            EvaluationMetric.prompt_key == prompt_key,
            EvaluationMetric.metric_name == metric_name,
        )
        existing = db.scalar(stmt)
        if existing:
            existing.metric_value = data["metric_value"]
            existing.sample_count = data.get("sample_count", existing.sample_count)
            existing.updated_at = now_local()
            db.commit()
            db.refresh(existing)
            return existing
        record = EvaluationMetric(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record


evaluation_result_repo = EvaluationResultRepo()
evaluation_metric_repo = EvaluationMetricRepo()
