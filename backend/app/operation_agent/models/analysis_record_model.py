"""
OperationAnalysisRecord — 运营分析记录模型

存储每次运营分析生成的完整报告数据。
包含页面上下文、指标、异常项、风险项、建议、证据链等全部内容。
通过 cache_key 实现 30 分钟缓存复用，同一参数组合在有效期内返回缓存结果。
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, BigInteger, String, JSON, Integer, Float, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class OperationAnalysisRecord(Base):
    __tablename__ = "operation_analysis_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # ── 用户/租户 ──
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── 报告元信息 ──
    report_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, default="operation_analysis")
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── 时间/维度 ──
    time_dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_date: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── 企业/项目 ──
    company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── 分析数据（JSON 存储） ──
    page_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    abnormal_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    advice_items_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── 报告正文 ──
    final_answer_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 模型/版本 ──
    graph_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Token 用量 ──
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float(12, 6), default=0)

    # ── 状态 ──
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 缓存/删除标记 ──
    cache_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)

    # ── 时间戳 ──
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)
