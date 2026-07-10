"""AnalysisRecordRepository — 运营分析记录数据访问层"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.operation_agent.models.analysis_record_model import OperationAnalysisRecord


class AnalysisRecordRepository:
    def create(self, db: Session, record: OperationAnalysisRecord) -> OperationAnalysisRecord:
        """创建一条分析记录"""
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, record_id: int) -> OperationAnalysisRecord | None:
        """按 ID 查询分析记录"""
        return db.get(OperationAnalysisRecord, record_id)

    def get_by_trace_id(self, db: Session, trace_id: str) -> OperationAnalysisRecord | None:
        """按 trace_id 查询分析记录"""
        stmt = select(OperationAnalysisRecord).where(OperationAnalysisRecord.trace_id == trace_id)
        return db.scalar(stmt)

    def get_by_cache_key(self, db: Session, cache_key: str) -> OperationAnalysisRecord | None:
        """按缓存 key 查询最近一条成功记录，用于 30 分钟缓存复用"""
        stmt = (
            select(OperationAnalysisRecord)
            .where(
                OperationAnalysisRecord.cache_key == cache_key,
                OperationAnalysisRecord.status == "success",
                OperationAnalysisRecord.is_deleted == 0,
            )
            .order_by(OperationAnalysisRecord.created_at.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    def list_recent(
        self,
        db: Session,
        *,
        domain: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OperationAnalysisRecord]:
        """查询最近的分析记录，可按领域/用户/租户过滤"""
        stmt = select(OperationAnalysisRecord).where(OperationAnalysisRecord.is_deleted == 0)
        if domain:
            stmt = stmt.where(OperationAnalysisRecord.domain == domain)
        if user_id:
            stmt = stmt.where(OperationAnalysisRecord.user_id == user_id)
        if tenant_id:
            stmt = stmt.where(OperationAnalysisRecord.tenant_id == tenant_id)
        stmt = stmt.order_by(OperationAnalysisRecord.created_at.desc()).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    def soft_delete(self, db: Session, record_id: int) -> None:
        """软删除分析记录"""
        db.execute(
            update(OperationAnalysisRecord)
            .where(OperationAnalysisRecord.id == record_id)
            .values(is_deleted=1)
        )
        db.commit()


analysis_record_repo = AnalysisRecordRepository()
