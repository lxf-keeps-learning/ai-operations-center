from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


class RedisPingError(RuntimeError):
    """Raised when the optional Redis health check cannot complete."""


@dataclass(frozen=True)
class RedisTarget:
    host: str
    port: int
    db: int
    username: str | None
    password: str | None


def ping_redis(redis_url: str, timeout: float = 2.0) -> str:
    target = _parse_redis_url(redis_url)

    try:
        with socket.create_connection((target.host, target.port), timeout=timeout) as sock:
            sock.settimeout(timeout)

            if target.password:
                if target.username:
                    _send_command(sock, "AUTH", target.username, target.password)
                else:
                    _send_command(sock, "AUTH", target.password)
                _expect_ok(_read_simple_response(sock), "AUTH")

            if target.db:
                _send_command(sock, "SELECT", str(target.db))
                _expect_ok(_read_simple_response(sock), "SELECT")

            _send_command(sock, "PING")
            response = _read_simple_response(sock)
    except OSError as exc:
        raise RedisPingError(f"Redis connection failed: {exc}") from exc

    if response.upper() != "PONG":
        raise RedisPingError(f"Redis PING returned unexpected response: {response}")

    return "pong"


def _parse_redis_url(redis_url: str) -> RedisTarget:
    parsed = urlparse(redis_url)

    if parsed.scheme != "redis":
        raise RedisPingError("REDIS_URL must use redis:// scheme")
    if not parsed.hostname:
        raise RedisPingError("REDIS_URL must include a host")

    db_text = parsed.path.lstrip("/")
    try:
        db = int(db_text) if db_text else 0
    except ValueError as exc:
        raise RedisPingError("REDIS_URL database index must be an integer") from exc

    return RedisTarget(
        host=parsed.hostname,
        port=parsed.port or 6379,
        db=db,
        username=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
    )


def _send_command(sock: socket.socket, *parts: str) -> None:
    payload = [f"*{len(parts)}\r\n".encode("utf-8")]
    for part in parts:
        encoded = part.encode("utf-8")
        payload.append(f"${len(encoded)}\r\n".encode("utf-8"))
        payload.append(encoded)
        payload.append(b"\r\n")
    sock.sendall(b"".join(payload))


def _read_simple_response(sock: socket.socket) -> str:
    line = _read_line(sock)
    if not line:
        raise RedisPingError("Redis returned an empty response")

    prefix = line[0]
    payload = line[1:]

    if prefix == "+":
        return payload
    if prefix == "-":
        raise RedisPingError(f"Redis error response: {payload}")

    raise RedisPingError(f"Redis returned unsupported response: {line}")


def _read_line(sock: socket.socket) -> str:
    buffer = bytearray()

    while not buffer.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RedisPingError("Redis closed the connection")
        buffer.extend(chunk)
        if len(buffer) > 4096:
            raise RedisPingError("Redis response line is too long")

    return buffer[:-2].decode("utf-8", errors="replace")


def _expect_ok(response: str, command: str) -> None:
    if response.upper() != "OK":
        raise RedisPingError(f"Redis {command} returned unexpected response: {response}")
