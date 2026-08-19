from datetime import UTC, datetime, timedelta

import pytest

from app.tool_registry.confirmation import (
    ConfirmationInvalidError,
    ConfirmationService,
)


def test_confirmation_round_trip_succeeds() -> None:
    service = ConfirmationService(secret="top-secret", ttl_seconds=300)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)

    token = service.issue("trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)

    service.verify(token, "trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)


def test_confirmation_rejects_argument_tampering() -> None:
    service = ConfirmationService(secret="top-secret", ttl_seconds=300)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    token = service.issue("trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)

    with pytest.raises(ConfirmationInvalidError):
        service.verify(token, "trace-1", "wo_commit", "1.0.0", "hash-2", "u1", now)


def test_confirmation_rejects_expired_tokens() -> None:
    service = ConfirmationService(secret="top-secret", ttl_seconds=300)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    token = service.issue("trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)

    with pytest.raises(ConfirmationInvalidError):
        service.verify(
            token,
            "trace-1",
            "wo_commit",
            "1.0.0",
            "hash-1",
            "u1",
            now + timedelta(seconds=301),
        )


def test_confirmation_rejects_empty_secret() -> None:
    with pytest.raises(ValueError, match="secret"):
        ConfirmationService(secret="", ttl_seconds=300)
