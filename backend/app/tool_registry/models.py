from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.timezone import now_local


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"
    __table_args__ = (
        CheckConstraint(
            "tool_type IN ('query', 'analysis', 'action') AND ("
            "(tool_type IN ('query', 'analysis') AND action_phase IS NULL) OR "
            "(tool_type = 'action' AND action_phase IS NOT NULL AND action_phase IN ('prepare', 'commit'))"
            ")",
            name="ck_tool_definitions_type_phase",
        ),
        Index("ix_tool_definitions_tool_key", "tool_key", unique=True),
        Index("ix_tool_definitions_capability", "capability", unique=True),
        Index("ix_tool_definitions_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_key: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tool_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_local,
        onupdate=now_local,
    )

    versions: Mapped[list["ToolVersion"]] = relationship(
        back_populates="tool",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    policies: Mapped[list["ToolPolicy"]] = relationship(
        back_populates="tool",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audits: Mapped[list["ToolCallAudit"]] = relationship(
        back_populates="tool",
        passive_deletes=True,
    )


class ToolVersion(Base):
    __tablename__ = "tool_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_tool_versions_status",
        ),
        UniqueConstraint("tool_id", "version", name="uk_tool_version"),
        Index("ix_tool_versions_tool_id_status", "tool_id", "status"),
        Index("ix_tool_versions_tool_id_status_stable", "tool_id", "status", "is_stable"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    implementation_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_stable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_local,
        onupdate=now_local,
    )

    tool: Mapped[ToolDefinition] = relationship(back_populates="versions")
    policies: Mapped[list["ToolPolicy"]] = relationship(
        back_populates="version_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audits: Mapped[list["ToolCallAudit"]] = relationship(
        back_populates="version_record",
        passive_deletes=True,
    )


class ToolPolicy(Base):
    __tablename__ = "tool_policies"
    __table_args__ = (
        Index(
            "ix_tool_policies_scope",
            "tool_id",
            "version_id",
            "tenant_id",
            "role",
            "enabled",
        ),
        Index("ix_tool_policies_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("tool_versions.id", ondelete="CASCADE"),
        nullable=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    gray_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_local,
        onupdate=now_local,
    )

    tool: Mapped[ToolDefinition] = relationship(back_populates="policies")
    version_record: Mapped[ToolVersion | None] = relationship(back_populates="policies")
    audits: Mapped[list["ToolCallAudit"]] = relationship(
        back_populates="policy",
        passive_deletes=True,
    )


class ToolCallAudit(Base):
    __tablename__ = "tool_call_audits"
    __table_args__ = (
        Index("ix_tool_call_audits_trace_id", "trace_id"),
        Index("ix_tool_call_audits_tool_created_at", "tool_id", "created_at"),
        Index("ix_tool_call_audits_policy_id", "policy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("tool_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    implementation_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caller_type: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("tool_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    gray_bucket: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_stable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    argument_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    argument_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)

    tool: Mapped[ToolDefinition | None] = relationship(back_populates="audits")
    version_record: Mapped[ToolVersion | None] = relationship(back_populates="audits")
    policy: Mapped[ToolPolicy | None] = relationship(back_populates="audits")
