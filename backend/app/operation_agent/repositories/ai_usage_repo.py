"""AiUsageRepository — AI 用量记录数据访问层"""

from sqlalchemy.orm import Session

from app.operation_agent.models.ai_usage_record_model import OperationAiUsageRecord


class AiUsageRepository:
    def create(self, db: Session, record: OperationAiUsageRecord) -> OperationAiUsageRecord:
        """创建一条 AI 用量记录"""
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def bulk_create(self, db: Session, records: list[OperationAiUsageRecord]) -> list[OperationAiUsageRecord]:
        """批量创建 AI 用量记录（单次分析可能有多条 LLM 调用）"""
        if not records:
            return []
        for r in records:
            db.add(r)
        db.commit()
        for r in records:
            db.refresh(r)
        return records


ai_usage_repo = AiUsageRepository()
