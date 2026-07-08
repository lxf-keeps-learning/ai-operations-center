from sqlalchemy.orm import Session

from app.operation_agent.models.ai_usage_record_model import OperationAiUsageRecord


class AiUsageRepository:
    def create(self, db: Session, record: OperationAiUsageRecord) -> OperationAiUsageRecord:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def bulk_create(self, db: Session, records: list[OperationAiUsageRecord]) -> list[OperationAiUsageRecord]:
        if not records:
            return []
        for r in records:
            db.add(r)
        db.commit()
        for r in records:
            db.refresh(r)
        return records


ai_usage_repo = AiUsageRepository()
