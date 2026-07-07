from datetime import datetime

from sqlalchemy import DateTime, Text, BigInteger, String, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class OperationReportFile(Base):
    __tablename__ = "operation_report_file"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    report_name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_format: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    report_version: Mapped[int] = mapped_column(Integer, default=1)

    storage_type: Mapped[str] = mapped_column(String(32), default="local")
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    generate_status: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    download_count: Mapped[int] = mapped_column(Integer, default=0)
    last_download_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    generated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)

    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)
