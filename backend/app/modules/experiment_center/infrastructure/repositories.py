from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.experiment_center.infrastructure.models import ExperimentResult, PromptExperiment


class ExperimentRepo:
    def get_by_id(self, db: Session, exp_id: int) -> PromptExperiment | None:
        return db.get(PromptExperiment, exp_id)

    def list(self, db: Session, offset: int = 0, limit: int = 20) -> tuple[list[PromptExperiment], int]:
        stmt = select(PromptExperiment).order_by(PromptExperiment.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0
        stmt = stmt.offset(offset).limit(limit)
        items = list(db.scalars(stmt).all())
        return items, total

    def create(self, db: Session, data: dict) -> PromptExperiment:
        record = PromptExperiment(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, exp_id: int, data: dict) -> PromptExperiment | None:
        record = self.get_by_id(db, exp_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record


class ExperimentResultRepo:
    def get_by_experiment(self, db: Session, experiment_id: int) -> list[ExperimentResult]:
        stmt = (
            select(ExperimentResult)
            .where(ExperimentResult.experiment_id == experiment_id)
            .order_by(ExperimentResult.version, ExperimentResult.id)
        )
        return list(db.scalars(stmt).all())

    def get_by_experiment_and_version(self, db: Session, experiment_id: int, version: str) -> list[ExperimentResult]:
        stmt = (
            select(ExperimentResult)
            .where(ExperimentResult.experiment_id == experiment_id, ExperimentResult.version == version)
            .order_by(ExperimentResult.id)
        )
        return list(db.scalars(stmt).all())

    def create(self, db: Session, data: dict) -> ExperimentResult:
        record = ExperimentResult(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, result_id: int, data: dict) -> ExperimentResult | None:
        record = db.get(ExperimentResult, result_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def get_aggregate_metrics(self, db: Session, experiment_id: int, version: str) -> list[dict[str, Any]]:
        results = self.get_by_experiment_and_version(db, experiment_id, version)
        metric_map: dict[str, list[float]] = {}
        for r in results:
            if r.metrics:
                for m in r.metrics:
                    if isinstance(m, dict) and "score" in m:
                        key = m.get("evaluator_key", "unknown")
                        score = m["score"]
                        if score is not None:
                            metric_map.setdefault(key, []).append(float(score))

        return [
            {"evaluator_key": key, "avg_score": round(sum(vals) / len(vals), 4), "sample_count": len(vals)}
            for key, vals in sorted(metric_map.items())
        ]


experiment_repo = ExperimentRepo()
experiment_result_repo = ExperimentResultRepo()
