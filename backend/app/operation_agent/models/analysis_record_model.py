from datetime import datetime

from sqlalchemy import DateTime, Text, BigInteger, String, JSON, Integer, Float, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class OperationAnalysisRecord(Base):
    __tablename__ = "operation_analysis_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    report_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, default="operation_analysis")

    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    time_dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_date: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    page_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    abnormal_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    advice_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    final_answer_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    graph_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float(12, 6), default=0)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    cache_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)
