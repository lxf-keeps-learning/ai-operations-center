from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json


class ConfirmationInvalidError(ValueError):
    pass


@dataclass(frozen=True)
class ConfirmationService:
    secret: str
    ttl_seconds: int

    def __post_init__(self) -> None:
        if not self.secret:
            raise ValueError("secret must not be empty")
        if self.ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")

    def issue(
        self,
        trace_id: str,
        tool_key: str,
        version: str,
        argument_hash: str,
        user_id: str,
        now: datetime,
    ) -> str:
        issued_at = int(now.astimezone(UTC).timestamp())
        expires_at = int((now.astimezone(UTC) + timedelta(seconds=self.ttl_seconds)).timestamp())
        payload = {
            "argument_hash": argument_hash,
            "expires_at": expires_at,
            "issued_at": issued_at,
            "tool_key": tool_key,
            "trace_id": trace_id,
            "user_id": user_id,
            "version": version,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self.secret.encode(), payload_bytes, hashlib.sha256).digest()
        return f"{_urlsafe_b64encode(payload_bytes)}.{_urlsafe_b64encode(signature)}"

    def verify(
        self,
        token: str,
        trace_id: str,
        tool_key: str,
        version: str,
        argument_hash: str,
        user_id: str,
        now: datetime,
    ) -> None:
        payload_bytes, signature = _split_token(token)
        expected_signature = hmac.new(self.secret.encode(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ConfirmationInvalidError("confirmation signature mismatch")

        try:
            payload = json.loads(payload_bytes)
        except json.JSONDecodeError as exc:
            raise ConfirmationInvalidError("invalid confirmation payload") from exc

        if not isinstance(payload, dict):
            raise ConfirmationInvalidError("invalid confirmation payload")

        expected = {
            "trace_id": trace_id,
            "tool_key": tool_key,
            "version": version,
            "argument_hash": argument_hash,
            "user_id": user_id,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise ConfirmationInvalidError(f"confirmation field mismatch: {key}")

        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, int):
            raise ConfirmationInvalidError("invalid confirmation expiry")
        if int(now.astimezone(UTC).timestamp()) > expires_at:
            raise ConfirmationInvalidError("confirmation token expired")


def _split_token(token: str) -> tuple[bytes, bytes]:
    payload_part, separator, signature_part = token.partition(".")
    if not separator:
        raise ConfirmationInvalidError("invalid confirmation token")
    return _urlsafe_b64decode(payload_part), _urlsafe_b64decode(signature_part)


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error) as exc:
        raise ConfirmationInvalidError("invalid confirmation token") from exc
