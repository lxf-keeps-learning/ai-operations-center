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


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("trace_id", "trace-2"),
        ("tool_key", "other_tool"),
        ("version", "2.0.0"),
        ("argument_hash", "hash-2"),
        ("user_id", "u2"),
    ],
)
def test_confirmation_rejects_bound_field_tampering(
    field: str,
    tampered_value: str,
) -> None:
    service = ConfirmationService(secret="top-secret", ttl_seconds=300)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    token = service.issue("trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)
    fields = {
        "trace_id": "trace-1",
        "tool_key": "wo_commit",
        "version": "1.0.0",
        "argument_hash": "hash-1",
        "user_id": "u1",
    }
    fields[field] = tampered_value

    with pytest.raises(ConfirmationInvalidError):
        service.verify(token, now=now, **fields)


def test_confirmation_rejects_signature_tampering() -> None:
    service = ConfirmationService(secret="top-secret", ttl_seconds=300)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    token = service.issue("trace-1", "wo_commit", "1.0.0", "hash-1", "u1", now)
    payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{payload}.{replacement}{signature[1:]}"

    with pytest.raises(ConfirmationInvalidError, match="signature"):
        service.verify(
            tampered,
            "trace-1",
            "wo_commit",
            "1.0.0",
            "hash-1",
            "u1",
            now,
        )


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
