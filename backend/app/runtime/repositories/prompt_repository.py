from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.models.prompt_model import AiPrompt
from app.runtime.schemas.prompt_schema import PromptCreate
from app.utils.ids import new_prompt_id
from app.utils.timezone import now_local


class PromptRepository:
    def create(self, db: Session, payload: PromptCreate) -> AiPrompt:
        max_version = self._max_version_by_code(db, payload.code)
        record = AiPrompt(
            id=new_prompt_id(),
            code=payload.code,
            name=payload.name,
            version=max_version + 1,
            content=payload.content,
            variables=payload.variables,
            scene_code=payload.scene_code,
            description=payload.description,
            created_by=payload.created_by,
            published_at=now_local(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, prompt_id: str) -> AiPrompt | None:
        return db.get(AiPrompt, prompt_id)

    def update(self, db: Session, prompt_id: str, payload: dict) -> AiPrompt | None:
        record = self.get_by_id(db, prompt_id)
        if record is None:
            return None
        for field, value in payload.items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, prompt_id: str, status: str) -> AiPrompt | None:
        record = self.get_by_id(db, prompt_id)
        if record is None:
            return None
        record.status = status
        if status == "active":
            record.published_at = now_local()
        db.commit()
        db.refresh(record)
        return record

    def get_active_by_code(self, db: Session, code: str) -> AiPrompt | None:
        stmt = (
            select(AiPrompt)
            .where(AiPrompt.code == code, AiPrompt.status == "active")
            .order_by(AiPrompt.version.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    def get_versions_by_code(self, db: Session, code: str) -> list[AiPrompt]:
        stmt = (
            select(AiPrompt)
            .where(AiPrompt.code == code)
            .order_by(AiPrompt.version.desc())
        )
        return list(db.scalars(stmt).all())

    def _max_version_by_code(self, db: Session, code: str) -> int:
        stmt = select(AiPrompt.version).where(AiPrompt.code == code).order_by(AiPrompt.version.desc()).limit(1)
        result = db.scalar(stmt)
        return result if result is not None else 0
