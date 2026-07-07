from datetime import datetime

from sqlalchemy import DateTime, Text, BigInteger, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.timezone import now_local


class OperationDownloadLog(Base):
    __tablename__ = "operation_report_download_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    analysis_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    download_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    download_status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    downloaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
