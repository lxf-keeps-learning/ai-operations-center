from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class PromptExperiment(Base):
    __tablename__ = "prompt_experiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    source_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    target_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    winner_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    test_case_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)


class ExperimentResult(Base):
    __tablename__ = "experiment_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_experiment.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    test_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
