"""LangSmith Tracing 配置。

LangSmith 用于 Agent 执行分析和效果评测；IOC 自有 ``ai_trace`` 继续承担
业务审计。两套链路通过 ``ioc_trace_id`` 关联。
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client

from app.config.settings import settings
from app.security.sensitive_data import scan_sensitive_data

logger = logging.getLogger(__name__)

_CREDENTIAL_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}


def _is_credential_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return (
        normalized in _CREDENTIAL_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
    )


def sanitize_trace_payload(value: Any) -> Any:
    """递归脱敏即将发送到 LangSmith 的数据，不修改业务侧原始对象。"""
    if isinstance(value, str):
        return scan_sensitive_data(value).masked_text
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED:credential]"
                if _is_credential_key(key)
                else sanitize_trace_payload(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_trace_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_trace_payload(item) for item in value)
    return value


def langsmith_status() -> tuple[bool, str]:
    """Return effective availability and a safe diagnostic reason."""
    if not settings.langsmith_tracing:
        return False, "disabled_by_config"
    if not settings.langsmith_api_key:
        return False, "missing_api_key"
    if settings.langsmith_sampling_rate <= 0:
        return False, "sampling_rate_zero"
    return True, "enabled"


def stable_reference(value: object | None) -> str | None:
    """将用户、会话和租户标识转换为不可逆且可关联的短引用。"""
    if value in (None, ""):
        return None
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return digest[:16]


@lru_cache(maxsize=1)
def _get_client() -> Client | None:
    enabled, reason = langsmith_status()
    if not enabled:
        logger.info("LangSmith tracing is not active: %s", reason)
        return None

    payload_transform = (
        sanitize_trace_payload
        if settings.langsmith_mask_inputs_outputs
        else None
    )
    try:
        return Client(
            api_url=settings.langsmith_endpoint,
            api_key=settings.langsmith_api_key,
            hide_inputs=payload_transform,
            hide_outputs=payload_transform,
            tracing_sampling_rate=settings.langsmith_sampling_rate,
        )
    except Exception:
        logger.exception("初始化 LangSmith Client 失败，继续使用 IOC 本地 Trace")
        return None


def build_langsmith_config(
    *,
    trace_id: str,
    graph_name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RunnableConfig:
    """构造单次 Graph 调用配置；关闭或初始化失败时返回无回调配置。"""
    trace_metadata: dict[str, Any] = {
        "ioc_trace_id": trace_id,
        "graph_name": graph_name,
        "app_env": settings.app_env,
        "user_ref": stable_reference(user_id),
        "session_ref": stable_reference(session_id),
        "conversation_ref": stable_reference(conversation_id),
    }
    trace_metadata.update(
        {
            key: stable_reference(value) if key.endswith("_ref") else value
            for key, value in (metadata or {}).items()
        }
    )
    trace_metadata = {
        key: value
        for key, value in sanitize_trace_payload(trace_metadata).items()
        if value is not None
    }

    config: RunnableConfig = {
        "run_name": graph_name,
        "tags": ["ioc", settings.app_env, graph_name],
        "metadata": trace_metadata,
    }

    client = _get_client()
    if client is None:
        return config

    try:
        config["callbacks"] = [
            LangChainTracer(
                project_name=settings.langsmith_project,
                client=client,
                tags=list(config["tags"]),
                metadata={
                    key: str(value)
                    for key, value in trace_metadata.items()
                },
            )
        ]
    except Exception:
        logger.exception("初始化 LangSmith Tracer 失败，继续使用 IOC 本地 Trace")
    return config
