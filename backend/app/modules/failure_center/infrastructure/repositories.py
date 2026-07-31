from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.failure_center.domain.enums import FailureType, FailureStatus
from app.modules.failure_center.infrastructure.models import FailureCase


class FailureCaseRepo:
    def get_by_id(self, db: Session, failure_id: int) -> FailureCase | None:
        return db.get(FailureCase, failure_id)

    def list(
        self, db: Session, *,
        prompt_key: str | None = None,
        failure_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FailureCase], int]:
        stmt = select(FailureCase)
        if prompt_key:
            stmt = stmt.where(FailureCase.prompt_key == prompt_key)
        if failure_type:
            stmt = stmt.where(FailureCase.failure_type == failure_type)
        if status:
            stmt = stmt.where(FailureCase.status == status)
        if severity:
            stmt = stmt.where(FailureCase.severity == severity)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        stmt = stmt.order_by(FailureCase.created_at.desc()).offset(offset).limit(limit)
        items = list(db.scalars(stmt).all())
        return items, total

    def create(self, db: Session, data: dict) -> FailureCase:
        record = FailureCase(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, failure_id: int, data: dict) -> FailureCase | None:
        record = self.get_by_id(db, failure_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def get_failure_stats(self, db: Session, prompt_key: str) -> dict[str, Any]:
        stmt = select(FailureCase).where(FailureCase.prompt_key == prompt_key)
        items = list(db.scalars(stmt).all())
        total = len(items)
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in items:
            by_type[item.failure_type] = by_type.get(item.failure_type, 0) + 1
            by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
        }

    def exists_by_trace_and_type(self, db: Session, trace_id: str, failure_type: str) -> bool:
        stmt = select(FailureCase).where(
            FailureCase.trace_id == trace_id,
            FailureCase.failure_type == failure_type,
        )
        return db.scalar(stmt) is not None


failure_case_repo = FailureCaseRepo()
