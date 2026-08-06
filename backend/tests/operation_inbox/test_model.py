import importlib.util
from pathlib import Path

from sqlalchemy import UniqueConstraint

from app.operation_inbox.models import OperationMessage


def test_operation_message_has_required_columns_and_indexes() -> None:
    expected_columns = {
        "id",
        "runtime_session_id",
        "report_chat_message_id",
        "report_id",
        "priority",
        "status",
        "assignee_id",
        "claimed_at",
        "lease_expires_at",
        "resolved_at",
        "resolution_note",
        "retry_count",
        "error_message",
        "created_at",
        "updated_at",
    }

    assert OperationMessage.__tablename__ == "operation_message"
    assert expected_columns <= set(OperationMessage.__table__.c.keys())

    indexes = {tuple(index.columns.keys()): index for index in OperationMessage.__table__.indexes}
    assert indexes[("runtime_session_id",)].unique is True
    assert ("status", "priority", "created_at") in indexes
    assert ("assignee_id", "status") in indexes
    assert ("report_id",) in indexes


def test_base_migration_uses_one_unique_runtime_session_index(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / "20260806_0002_create_operation_message.py"
    )
    spec = importlib.util.spec_from_file_location("operation_message_base_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    table_args = []
    indexes = []
    monkeypatch.setattr(migration.op, "create_table", lambda *args: table_args.extend(args))
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: indexes.append((args, kwargs)))

    migration.upgrade()

    assert not any(isinstance(argument, UniqueConstraint) for argument in table_args)
    assert (("ix_operation_message_runtime_session_id", "operation_message", ["runtime_session_id"]), {"unique": True}) in indexes
