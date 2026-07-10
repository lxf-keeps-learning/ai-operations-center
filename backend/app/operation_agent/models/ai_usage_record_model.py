"""
OperationAiUsageRecord — AI 用量记录模型

记录每次运营分析中 LLM 调用的 Token 使用量和费用。
每次分析可能包含多次 LLM 调用（原因分析 + 建议生成），每次调用一条记录。
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, BigInteger, String, Integer, Float, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class OperationAiUsageRecord(Base):
    __tablename__ = "operation_ai_usage_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    analysis_record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)

    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # ── Token 与费用 ──
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    input_cost: Mapped[float] = mapped_column(Float(12, 6), default=0)
    output_cost: Mapped[float] = mapped_column(Float(12, 6), default=0)
    total_cost: Mapped[float] = mapped_column(Float(12, 6), default=0)

    # ── 状态 ──
    success: Mapped[int] = mapped_column(SmallInteger, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
