from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.timezone import now_local


class PromptDefinition(Base):
    __tablename__ = "prompt_definition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    prompt_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_scene: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    graph_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    node_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    versions = relationship("PromptVersion", back_populates="prompt", lazy="dynamic")
    variables = relationship("PromptVariable", back_populates="prompt", lazy="dynamic", cascade="all, delete-orphan")


class PromptVersion(Base):
    __tablename__ = "prompt_version"

    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uk_prompt_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    system_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_role_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_goal_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    output_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    positive_examples: Mapped[list | None] = mapped_column(JSON, nullable=True)
    negative_examples: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    langsmith_commit_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    langsmith_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)

    prompt = relationship("PromptDefinition", back_populates="versions")


class PromptVariable(Base):
    __tablename__ = "prompt_variable"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    variable_key: Mapped[str] = mapped_column(String(128), nullable=False)
    variable_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="string")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="graph_state")
    source_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)

    prompt = relationship("PromptDefinition", back_populates="variables")


class PromptRelease(Base):
    __tablename__ = "prompt_release"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    release_type: Mapped[str] = mapped_column(String(32), nullable=False)
    traffic_ratio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    released_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    released_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    rollback_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptTestCase(Base):
    __tablename__ = "prompt_test_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    case_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)


class PromptTestRun(Base):
    __tablename__ = "prompt_test_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    test_case_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("prompt_test_case.id"), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    rendered_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)

    evaluations = relationship("PromptEvaluation", back_populates="test_run", lazy="dynamic")


class PromptEvaluation(Base):
    __tablename__ = "prompt_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_test_run.id"), nullable=False, index=True)
    evaluator_key: Mapped[str] = mapped_column(String(128), nullable=False)
    evaluator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    violations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)

    test_run = relationship("PromptTestRun", back_populates="evaluations")


class PromptAuditLog(Base):
    __tablename__ = "prompt_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_definition.id"), nullable=False, index=True)
    version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local)
