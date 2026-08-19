from __future__ import annotations

from collections.abc import Callable
import threading

from app.config.settings import settings
from app.core.logging.logger import get_logger
from app.db.session import get_session_local
from app.tool_center.contracts import BaseToolInput, ToolContext, ToolResult
from app.tool_center.registry import get_tool, list_tools
from app.tool_registry.confirmation import ConfirmationService
from app.tool_registry.contracts import (
    ActionPhase,
    RegistrySnapshot,
    ToolDescriptor,
    ToolType,
)
from app.tool_registry.executor_catalog import executor_catalog
from app.tool_registry.gateway import ToolGateway
from app.tool_registry.rate_limit import InMemoryFixedWindowRateLimiter
from app.tool_registry.registry import DatabaseToolRegistry, set_active_registry
from app.tool_registry.repository import ToolRegistryRepository

logger = get_logger("ioc.tool_registry")

# 旧工具名与 capability 的固定双向映射；capability 是数据库模式的运行时标识。
LEGACY_NAME_TO_CAPABILITY = {
    "kpi_query": "query.kpi",
    "alarm_query": "query.alarm",
    "risk_query": "query.risk",
    "work_order_query": "query.work_order",
    "ioc_summary_analysis": "analysis.ioc_summary",
    "work_order_draft": "action.work_order.draft",
}

CAPABILITY_TO_LEGACY_NAME = {
    capability: name for name, capability in LEGACY_NAME_TO_CAPABILITY.items()
}

_LEGACY_TOOL_TYPES: dict[str, tuple[ToolType, ActionPhase | None]] = {
    "ioc_summary_analysis": (ToolType.ANALYSIS, None),
    "work_order_draft": (ToolType.ACTION, ActionPhase.PREPARE),
}

_runtime_lock = threading.RLock()
_runtime_registry: DatabaseToolRegistry | None = None
_runtime_gateway: ToolGateway | None = None
_runtime_rate_limiter: InMemoryFixedWindowRateLimiter | None = None


def execute_tool(
    name_or_capability: str,
    arguments: dict,
    context: ToolContext,
    confirmation_token: str | None = None,
    stable_only: bool = False,
) -> ToolResult:
    """按当前模式执行工具：legacy 走旧 Registry，database 走 Tool Gateway 治理链路。"""
    if settings.tool_registry_mode == "legacy":
        return _execute_legacy(name_or_capability, arguments, context)
    capability = LEGACY_NAME_TO_CAPABILITY.get(name_or_capability, name_or_capability)
    return get_tool_gateway().execute(
        capability,
        arguments,
        context,
        confirmation_token=confirmation_token,
        stable_only=stable_only,
    )


def _execute_legacy(
    name_or_capability: str,
    arguments: dict,
    context: ToolContext,
) -> ToolResult:
    tool_name = CAPABILITY_TO_LEGACY_NAME.get(name_or_capability, name_or_capability)
    tool = get_tool(tool_name)
    return tool.run(BaseToolInput(context=context, filters=arguments))


def discover_tools(context: ToolContext) -> list[ToolDescriptor]:
    """列出调用方可见的工具描述；legacy 模式基于旧 Registry 名称与描述。"""
    if settings.tool_registry_mode == "legacy":
        return _discover_legacy()
    return get_tool_registry().discover(context)


def _discover_legacy() -> list[ToolDescriptor]:
    descriptors = []
    for name in sorted(list_tools()):
        tool = get_tool(name)
        tool_type, action_phase = _LEGACY_TOOL_TYPES.get(name, (ToolType.QUERY, None))
        descriptors.append(
            ToolDescriptor(
                tool_id=0,
                tool_key=name,
                capability=LEGACY_NAME_TO_CAPABILITY.get(name, name),
                name=tool.name,
                description=tool.description,
                tool_type=tool_type,
                action_phase=action_phase,
                version_id=0,
                version="legacy",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                rate_limit_per_minute=60,
                selected_stable=True,
            )
        )
    return descriptors


def get_tool_registry() -> DatabaseToolRegistry:
    """惰性构建进程级 DatabaseToolRegistry；不会在 import 时连接 MySQL。"""
    global _runtime_registry
    registry = _runtime_registry
    if registry is None:
        with _runtime_lock:
            registry = _runtime_registry
            if registry is None:
                registry = _build_registry()
                _runtime_registry = registry
                set_active_registry(registry)
    return registry


def get_tool_gateway() -> ToolGateway:
    """惰性构建进程级 ToolGateway。"""
    global _runtime_gateway
    gateway = _runtime_gateway
    if gateway is None:
        with _runtime_lock:
            gateway = _runtime_gateway
            if gateway is None:
                gateway = _build_gateway()
                _runtime_gateway = gateway
    return gateway


def _build_registry() -> DatabaseToolRegistry:
    session_local = get_session_local()

    def snapshot_loader() -> RegistrySnapshot:
        with session_local() as db:
            return ToolRegistryRepository(db).load_snapshot()

    return DatabaseToolRegistry(
        snapshot_loader,
        cache_ttl_seconds=settings.tool_registry_cache_ttl_seconds,
        stale_query_ttl_seconds=settings.tool_registry_stale_query_ttl_seconds,
        default_rate_limit_per_minute=settings.tool_default_rate_limit_per_minute,
    )


def _build_gateway() -> ToolGateway:
    session_local = get_session_local()

    def repository_factory() -> ToolRegistryRepository:
        return ToolRegistryRepository(session_local())

    secret = settings.tool_confirmation_secret
    confirmation_service = (
        ConfirmationService(secret=secret, ttl_seconds=settings.tool_confirmation_ttl_seconds)
        if secret
        else None
    )
    return ToolGateway(
        registry=get_tool_registry(),
        executors=executor_catalog,
        rate_limiter=_get_rate_limiter(),
        repository_factory=repository_factory,
        confirmation_service=confirmation_service,
    )


def _get_rate_limiter() -> InMemoryFixedWindowRateLimiter:
    global _runtime_rate_limiter
    if _runtime_rate_limiter is None:
        _runtime_rate_limiter = InMemoryFixedWindowRateLimiter()
    return _runtime_rate_limiter


def reset_runtime_for_tests() -> None:
    """清除缓存的运行时单例，仅供测试隔离使用。"""
    global _runtime_registry, _runtime_gateway, _runtime_rate_limiter
    with _runtime_lock:
        _runtime_registry = None
        _runtime_gateway = None
        _runtime_rate_limiter = None
        set_active_registry(None)
