import json
from datetime import datetime
from typing import Any

from typing import Any

from sqlalchemy import Integer, func, select, update
from sqlalchemy.orm import Session

from app.modules.prompt_center.infrastructure.models import (
    PromptAuditLog,
    PromptDefinition,
    PromptEvaluation,
    PromptRelease,
    PromptTestCase,
    PromptTestRun,
    PromptVariable,
    PromptVersion,
)
from app.utils.ids import new_prompt_id
from app.utils.timezone import now_local


class PromptDefinitionRepo:
    def get_by_id(self, db: Session, prompt_id: int) -> PromptDefinition | None:
        return db.get(PromptDefinition, prompt_id)

    def get_by_key(self, db: Session, prompt_key: str) -> PromptDefinition | None:
        stmt = select(PromptDefinition).where(
            PromptDefinition.prompt_key == prompt_key,
            PromptDefinition.deleted == False,
        )
        return db.scalar(stmt)

    def list(
        self, db: Session, *,
        search: str | None = None,
        business_scene: str | None = None,
        graph_name: str | None = None,
        node_name: str | None = None,
        status: str | None = None,
        owner_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PromptDefinition], int]:
        stmt = select(PromptDefinition).where(PromptDefinition.deleted == False)

        if search:
            stmt = stmt.where(
                (PromptDefinition.prompt_name.ilike(f"%{search}%"))
                | (PromptDefinition.prompt_key.ilike(f"%{search}%"))
            )
        if business_scene:
            stmt = stmt.where(PromptDefinition.business_scene == business_scene)
        if graph_name:
            stmt = stmt.where(PromptDefinition.graph_name == graph_name)
        if node_name:
            stmt = stmt.where(PromptDefinition.node_name == node_name)
        if status:
            stmt = stmt.where(PromptDefinition.status == status)
        if owner_id:
            stmt = stmt.where(PromptDefinition.owner_id == owner_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        stmt = stmt.order_by(PromptDefinition.updated_at.desc()).offset(offset).limit(limit)
        items = list(db.scalars(stmt).all())
        return items, total

    def create(self, db: Session, data: dict) -> PromptDefinition:
        record = PromptDefinition(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, prompt_id: int, data: dict) -> PromptDefinition | None:
        record = self.get_by_id(db, prompt_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def soft_delete(self, db: Session, prompt_id: int) -> bool:
        record = self.get_by_id(db, prompt_id)
        if record is None:
            return False
        record.deleted = True
        db.commit()
        return True


class PromptVersionRepo:
    def get_by_id(self, db: Session, version_id: int) -> PromptVersion | None:
        return db.get(PromptVersion, version_id)

    def get_by_id_for_update(self, db: Session, version_id: int) -> PromptVersion | None:
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.id == version_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return db.scalar(stmt)

    def get_by_prompt(self, db: Session, prompt_id: int) -> list[PromptVersion]:
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def get_published(self, db: Session, prompt_id: int, environment: str) -> PromptVersion | None:
        subq = (
            select(PromptRelease.version_id)
            .where(
                PromptRelease.prompt_id == prompt_id,
                PromptRelease.environment == environment,
                PromptRelease.status == "active",
            )
            .order_by(PromptRelease.released_at.desc())
            .limit(1)
        )
        version_id = db.scalar(subq)
        if version_id is None:
            return None
        return self.get_by_id(db, version_id)

    def get_max_version(self, db: Session, prompt_id: int) -> str:
        stmt = (
            select(PromptVersion.version)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.id.desc())
            .limit(1)
        )
        result = db.scalar(stmt)
        if result is None:
            return "1.0.0"
        parts = result.split(".")
        return f"{parts[0]}.{int(parts[1]) + 1}.0" if len(parts) >= 2 else "1.1.0"

    def create(self, db: Session, data: dict) -> PromptVersion:
        prompt_id = data["prompt_id"]
        version = self.get_max_version(db, prompt_id)
        record = PromptVersion(version=version, **data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def create_draft_version(self, db: Session, data: dict) -> PromptVersion:
        payload = dict(data)
        prompt_id = payload["prompt_id"]
        payload.setdefault("status", "draft")
        record = PromptVersion(
            version=self.get_max_version(db, prompt_id),
            **payload,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, version_id: int, status: str) -> PromptVersion | None:
        record = self.get_by_id(db, version_id)
        if record is None:
            return None
        record.status = status
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, version_id: int, data: dict) -> PromptVersion | None:
        record = self.get_by_id(db, version_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record


class PromptVariableRepo:
    def get_by_prompt(self, db: Session, prompt_id: int) -> list[PromptVariable]:
        stmt = (
            select(PromptVariable)
            .where(PromptVariable.prompt_id == prompt_id)
            .order_by(PromptVariable.display_order)
        )
        return list(db.scalars(stmt).all())

    def batch_create(self, db: Session, prompt_id: int, variables: list[dict]) -> list[PromptVariable]:
        for v in variables:
            v["prompt_id"] = prompt_id
        records = [PromptVariable(**v) for v in variables]
        for r in records:
            db.add(r)
        db.commit()
        for r in records:
            db.refresh(r)
        return records

    def batch_delete(self, db: Session, prompt_id: int) -> None:
        stmt = select(PromptVariable).where(PromptVariable.prompt_id == prompt_id)
        for r in db.scalars(stmt).all():
            db.delete(r)
        db.commit()


class PromptReleaseRepo:
    def get_active(self, db: Session, prompt_id: int, environment: str) -> PromptRelease | None:
        stmt = (
            select(PromptRelease)
            .where(
                PromptRelease.prompt_id == prompt_id,
                PromptRelease.environment == environment,
                PromptRelease.status == "active",
            )
            .order_by(PromptRelease.released_at.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    def list_by_prompt(self, db: Session, prompt_id: int) -> list[PromptRelease]:
        stmt = (
            select(PromptRelease)
            .where(PromptRelease.prompt_id == prompt_id)
            .order_by(PromptRelease.released_at.desc())
        )
        return list(db.scalars(stmt).all())

    def create(self, db: Session, data: dict) -> PromptRelease:
        record = PromptRelease(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def deactivate_env(self, db: Session, prompt_id: int, environment: str) -> None:
        stmt = (
            update(PromptRelease)
            .where(
                PromptRelease.prompt_id == prompt_id,
                PromptRelease.environment == environment,
                PromptRelease.status == "active",
            )
            .values(status="inactive")
        )
        db.execute(stmt)
        db.commit()


class PromptTestCaseRepo:
    def get_by_id(self, db: Session, case_id: int) -> PromptTestCase | None:
        return db.get(PromptTestCase, case_id)

    def list_by_prompt(self, db: Session, prompt_id: int) -> list[PromptTestCase]:
        stmt = (
            select(PromptTestCase)
            .where(PromptTestCase.prompt_id == prompt_id, PromptTestCase.enabled == True)
            .order_by(PromptTestCase.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def create(self, db: Session, data: dict) -> PromptTestCase:
        record = PromptTestCase(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record


class PromptTestRunRepo:
    def get_by_id(self, db: Session, run_id: int) -> PromptTestRun | None:
        return db.get(PromptTestRun, run_id)

    def get_by_prompt(self, db: Session, prompt_id: int, offset: int = 0, limit: int = 20) -> tuple[list[PromptTestRun], int]:
        stmt = select(PromptTestRun).where(PromptTestRun.prompt_id == prompt_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0
        stmt = stmt.order_by(PromptTestRun.created_at.desc()).offset(offset).limit(limit)
        items = list(db.scalars(stmt).all())
        return items, total

    def create(self, db: Session, data: dict) -> PromptTestRun:
        record = PromptTestRun(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update(self, db: Session, run_id: int, data: dict) -> PromptTestRun | None:
        record = self.get_by_id(db, run_id)
        if record is None:
            return None
        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record


class PromptEvaluationRepo:
    def get_by_test_run(self, db: Session, test_run_id: int) -> list[PromptEvaluation]:
        stmt = select(PromptEvaluation).where(PromptEvaluation.test_run_id == test_run_id)
        return list(db.scalars(stmt).all())

    def create(self, db: Session, data: dict) -> PromptEvaluation:
        record = PromptEvaluation(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def batch_create(self, db: Session, items: list[dict]) -> list[PromptEvaluation]:
        records = [PromptEvaluation(**item) for item in items]
        for r in records:
            db.add(r)
        db.commit()
        for r in records:
            db.refresh(r)
        return records

    def get_compliance_stats(self, db: Session, prompt_id: int) -> dict[str, Any]:
        stmt = (
            select(
                func.count(PromptEvaluation.id).label("total"),
                func.sum(PromptEvaluation.passed.cast(Integer)).label("passed"),
            )
            .select_from(PromptEvaluation)
            .join(PromptTestRun, PromptEvaluation.test_run_id == PromptTestRun.id)
            .where(PromptTestRun.prompt_id == prompt_id)
        )
        result = db.execute(stmt).first()
        if result is None:
            return {"total": 0, "passed": 0, "rate": 0.0}

        total = result[0] or 0
        passed = result[1] or 0
        return {
            "total": total,
            "passed": passed,
            "rate": round(passed / total * 100, 2) if total > 0 else 0.0,
        }


class PromptAuditLogRepo:
    def create(self, db: Session, data: dict) -> PromptAuditLog:
        record = PromptAuditLog(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_by_prompt(self, db: Session, prompt_id: int, offset: int = 0, limit: int = 50) -> list[PromptAuditLog]:
        stmt = (
            select(PromptAuditLog)
            .where(PromptAuditLog.prompt_id == prompt_id)
            .order_by(PromptAuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


prompt_def_repo = PromptDefinitionRepo()
prompt_version_repo = PromptVersionRepo()
prompt_variable_repo = PromptVariableRepo()
prompt_release_repo = PromptReleaseRepo()
prompt_test_case_repo = PromptTestCaseRepo()
prompt_test_run_repo = PromptTestRunRepo()
prompt_evaluation_repo = PromptEvaluationRepo()
prompt_audit_log_repo = PromptAuditLogRepo()
