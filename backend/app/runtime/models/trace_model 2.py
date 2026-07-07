from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class AiTrace(Base):
    __tablename__ = "ai_trace"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    span_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    graph_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", index=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, index=True)
