"""Optional LangSmith child runs for Agent domain boundaries."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar

from langsmith.run_helpers import get_current_run_tree
from langsmith.run_trees import RunTree

from app.config.settings import settings
from app.observability.langsmith_tracing import (
    _get_client,
    sanitize_trace_payload,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _get_langsmith_client():
    """Return the configured client, allowing tests to replace this boundary."""
    return _get_client()


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _sanitize_mapping(value: Any) -> dict[str, Any]:
    sanitized = sanitize_trace_payload(_json_safe(value or {}))
    return sanitized if isinstance(sanitized, dict) else {"value": sanitized}


def run_observed(
    name: str,
    run_type: str,
    operation: Callable[[], T],
    *,
    inputs: Any = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    trace_id: str | None = None,
) -> T:
    """Execute an operation and best-effort report it as a LangSmith child run.

    The wrapped operation is authoritative: tracing setup, serialization and
    upload errors are swallowed, while errors raised by the operation itself
    are re-raised unchanged.
    """
    client = _get_langsmith_client()
    run = None
    if client is not None:
        try:
            parent = get_current_run_tree()
            run_inputs = _sanitize_mapping(inputs)
            run_metadata = _sanitize_mapping(metadata)
            if trace_id:
                run_metadata.setdefault("ioc_trace_id", trace_id)

            if parent is not None:
                run = parent.create_child(
                    name=name,
                    run_type=run_type,
                    inputs=run_inputs,
                    tags=tags or [],
                )
                run.extra = {**getattr(run, "extra", {}), "metadata": run_metadata}
            else:
                run = RunTree(
                    name=name,
                    run_type=run_type,
                    inputs=run_inputs,
                    extra={"metadata": run_metadata},
                    tags=tags or ["ioc", settings.app_env],
                    project_name=settings.langsmith_project,
                    ls_client=client,
                )
            run.post()
        except Exception:
            logger.debug("LangSmith child run 初始化失败: %s", name, exc_info=True)
            run = None

    try:
        result = operation()
    except Exception as exc:
        if run is not None:
            try:
                run.end(error=str(exc))
                run.post()
            except Exception:
                logger.debug("LangSmith child run 更新失败: %s", name, exc_info=True)
        raise

    if run is not None:
        try:
            run.end(outputs=_sanitize_mapping(result))
            run.post()
        except Exception:
            logger.debug("LangSmith child run 完成上报失败: %s", name, exc_info=True)
    return result


async def arun_observed(
    name: str,
    run_type: str,
    operation: Awaitable[T],
    *,
    inputs: Any = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    trace_id: str | None = None,
) -> T:
    """异步版 run_observed：包装异步 operation 并 best-effort 上报 LangSmith。

    被包装的 operation 是权威结果来源：tracing 初始化、序列化、上传错误全部吞掉，
    operation 自身抛出的异常（含 CancelledError）原样向上传播。
    """
    client = _get_langsmith_client()
    run = None
    if client is not None:
        try:
            parent = get_current_run_tree()
            run_inputs = _sanitize_mapping(inputs)
            run_metadata = _sanitize_mapping(metadata)
            if trace_id:
                run_metadata.setdefault("ioc_trace_id", trace_id)

            if parent is not None:
                run = parent.create_child(
                    name=name,
                    run_type=run_type,
                    inputs=run_inputs,
                    tags=tags or [],
                )
                run.extra = {**getattr(run, "extra", {}), "metadata": run_metadata}
            else:
                run = RunTree(
                    name=name,
                    run_type=run_type,
                    inputs=run_inputs,
                    extra={"metadata": run_metadata},
                    tags=tags or ["ioc", settings.app_env],
                    project_name=settings.langsmith_project,
                    ls_client=client,
                )
            await run.apost()
        except Exception:
            logger.debug("LangSmith child run 初始化失败: %s", name, exc_info=True)
            run = None

    try:
        result = await operation
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if run is not None:
            try:
                await run.aend(error=str(exc))
                await run.apost()
            except Exception:
                logger.debug("LangSmith child run 更新失败: %s", name, exc_info=True)
        raise

    if run is not None:
        try:
            await run.aend(outputs=_sanitize_mapping(result))
            await run.apost()
        except Exception:
            logger.debug("LangSmith child run 完成上报失败: %s", name, exc_info=True)
    return result
