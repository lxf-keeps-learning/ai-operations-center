from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.core.logging.logger import get_logger
from app.tool_center.contracts import ToolContext
from app.tool_center.exceptions import (
    CapabilityUnavailableError,
    RegistryUnavailableError,
    ToolForbiddenError,
)
from app.tool_registry.cache import RegistryCache, age_seconds
from app.tool_registry.contracts import (
    GovernanceDecision,
    RegistrySnapshot,
    ResolvedTool,
    ToolDefinitionRecord,
    ToolDescriptor,
    ToolPolicyRecord,
    ToolType,
    ToolVersionRecord,
    VersionStatus,
)
from app.tool_registry.policy import EffectivePolicy, resolve_policy
from app.tool_registry.rollout import VersionSelection, choose_version

logger = get_logger("ioc.tool_registry")

_Clock = Callable[[], datetime]


class DatabaseToolRegistry:
    """基于 MySQL 配置的按能力发现与版本解析。

    resolve 执行固定顺序：能力查找 -> 已发布版本过滤 -> 灰度候选策略 ->
    一致性哈希灰度桶 -> 最终策略权限校验。限流与确认凭证由 Tool Gateway 负责。
    """

    def __init__(
        self,
        snapshot_loader: Callable[[], RegistrySnapshot],
        *,
        cache_ttl_seconds: int = 30,
        stale_query_ttl_seconds: int = 86400,
        default_rate_limit_per_minute: int = 60,
        clock: _Clock | None = None,
    ) -> None:
        self._loader = snapshot_loader
        self._default_rate_limit_per_minute = default_rate_limit_per_minute
        self._clock = clock or (lambda: datetime.now(UTC))
        self._cache = RegistryCache(
            ttl_seconds=cache_ttl_seconds,
            stale_query_ttl_seconds=stale_query_ttl_seconds,
            clock=clock,
        )

    def invalidate(self) -> None:
        self._cache.invalidate()

    def resolve(
        self,
        capability: str,
        context: ToolContext,
        *,
        stable_only: bool = False,
    ) -> ResolvedTool:
        snapshot, stale = self._load_snapshot()
        definition = self._find_definition(snapshot, capability)
        if definition is None:
            raise CapabilityUnavailableError(capability)
        if stale:
            logger.warning(
                "tool registry serving stale snapshot capability=%s age_seconds=%d",
                capability,
                age_seconds(snapshot.loaded_at, self._clock()),
            )
            if definition.tool_type is ToolType.ACTION:
                raise RegistryUnavailableError(
                    "tool registry cache expired; action tools are rejected during degradation"
                )
            stable_only = True

        versions = self._published_versions(snapshot, definition.id)
        policies = self._tool_policies(snapshot, definition.id)
        selection = self._choose_version(
            definition,
            versions,
            policies,
            context,
            stable_only=stable_only,
        )
        effective_policy = self._resolve_final_policy(
            definition,
            policies,
            selection.version_id,
            context,
        )
        if effective_policy.decision is GovernanceDecision.DENY:
            raise ToolForbiddenError(
                f"tool access denied by governance policy for capability {definition.capability}",
                detail={
                    "policy_id": effective_policy.policy_id,
                    "capability": definition.capability,
                },
            )
        return ResolvedTool(
            tool_id=definition.id,
            tool_key=definition.tool_key,
            capability=definition.capability,
            tool_type=definition.tool_type,
            action_phase=definition.action_phase,
            version_id=selection.version_id,
            version=selection.version,
            implementation_ref=selection.implementation_ref,
            policy_id=effective_policy.policy_id,
            rate_limit_per_minute=effective_policy.rate_limit_per_minute,
            gray_bucket=selection.gray_bucket,
            selected_stable=selection.selected_stable,
        )

    def discover(
        self,
        context: ToolContext,
        capability: str | None = None,
    ) -> list[ToolDescriptor]:
        snapshot, stale = self._load_snapshot()
        if stale:
            logger.warning(
                "tool registry discovery serving stale snapshot age_seconds=%d",
                age_seconds(snapshot.loaded_at, self._clock()),
            )
        descriptors: list[ToolDescriptor] = []
        for definition in snapshot.definitions:
            if capability is not None and definition.capability != capability:
                continue
            versions = self._published_versions(snapshot, definition.id)
            if not versions:
                continue
            policies = self._tool_policies(snapshot, definition.id)
            try:
                selection = self._choose_version(
                    definition,
                    versions,
                    policies,
                    context,
                    stable_only=stale,
                )
                effective_policy = self._resolve_final_policy(
                    definition,
                    policies,
                    selection.version_id,
                    context,
                )
            except (CapabilityUnavailableError, ToolForbiddenError):
                continue
            if effective_policy.decision is GovernanceDecision.DENY:
                continue
            selected_version = next(
                version for version in versions if version.id == selection.version_id
            )
            descriptors.append(
                ToolDescriptor(
                    tool_id=definition.id,
                    tool_key=definition.tool_key,
                    capability=definition.capability,
                    name=definition.name,
                    description=definition.description,
                    tool_type=definition.tool_type,
                    action_phase=definition.action_phase,
                    version_id=selected_version.id,
                    version=selected_version.version,
                    input_schema=selected_version.input_schema,
                    output_schema=selected_version.output_schema,
                    rate_limit_per_minute=effective_policy.rate_limit_per_minute,
                    selected_stable=selection.selected_stable,
                )
            )
        return descriptors

    def _load_snapshot(self) -> tuple[RegistrySnapshot, bool]:
        try:
            return self._cache.get_or_load(self._loader), False
        except RegistryUnavailableError:
            return self._cache.get_stable_fallback(self._clock()), True

    @staticmethod
    def _find_definition(
        snapshot: RegistrySnapshot,
        capability: str,
    ) -> ToolDefinitionRecord | None:
        for definition in snapshot.definitions:
            if definition.capability == capability and definition.enabled:
                return definition
        return None

    @staticmethod
    def _published_versions(
        snapshot: RegistrySnapshot,
        tool_id: int,
    ) -> list[ToolVersionRecord]:
        return [
            version
            for version in snapshot.versions
            if version.tool_id == tool_id and version.status is VersionStatus.PUBLISHED
        ]

    @staticmethod
    def _tool_policies(snapshot: RegistrySnapshot, tool_id: int) -> list[ToolPolicyRecord]:
        return [policy for policy in snapshot.policies if policy.tool_id == tool_id]

    def _choose_version(
        self,
        definition: ToolDefinitionRecord,
        versions: Sequence[ToolVersionRecord],
        policies: Sequence[ToolPolicyRecord],
        context: ToolContext,
        stable_only: bool,
    ) -> VersionSelection:
        try:
            return choose_version(definition, versions, policies, context, stable_only=stable_only)
        except ValueError as exc:
            if not any(version.is_stable for version in versions):
                raise CapabilityUnavailableError(definition.capability) from exc
            if context.caller_type == "internal":
                return choose_version(definition, versions, [], context, stable_only=True)
            raise ToolForbiddenError(
                f"no governance policy matches capability {definition.capability}; "
                "only trusted internal callers are allowed",
                detail={"capability": definition.capability},
            ) from exc

    def _resolve_final_policy(
        self,
        definition: ToolDefinitionRecord,
        policies: Sequence[ToolPolicyRecord],
        version_id: int,
        context: ToolContext,
    ) -> EffectivePolicy:
        try:
            return resolve_policy(tuple(policies), version_id, context)
        except ValueError:
            if context.caller_type != "internal":
                raise ToolForbiddenError(
                    f"no governance policy matches capability {definition.capability}; "
                    "only trusted internal callers are allowed",
                    detail={"capability": definition.capability},
                )
            return EffectivePolicy(
                policy_id=None,
                decision=GovernanceDecision.ALLOW,
                rate_limit_per_minute=self._default_rate_limit_per_minute,
                gray_percentage=0,
                requires_confirmation=False,
            )


_active_registry: DatabaseToolRegistry | None = None


def set_active_registry(registry: DatabaseToolRegistry | None) -> None:
    """登记当前进程的活跃 Registry，供管理操作在提交后主动失效缓存。"""
    global _active_registry
    _active_registry = registry


def get_active_registry() -> DatabaseToolRegistry | None:
    return _active_registry


def invalidate_active_registry() -> None:
    registry = _active_registry
    if registry is not None:
        registry.invalidate()
