from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import time
from typing import Any

from app.core.logging.logger import get_logger
from app.core.trace.trace_context import get_trace_id
from app.tool_center.contracts import BaseToolInput, ToolContext, ToolError, ToolResult
from app.tool_center.exceptions import (
    CapabilityUnavailableError,
    RegistryConfigurationError,
    RegistryUnavailableError,
    ToolForbiddenError,
    ToolNotFoundError,
)
from app.tool_center.telemetry import build_argument_summary, hash_arguments
from app.tool_registry.confirmation import ConfirmationInvalidError, ConfirmationService
from app.tool_registry.contracts import ActionPhase, ResolvedTool
from app.tool_registry.executor_catalog import ExecutorCatalog
from app.tool_registry.models import ToolCallAudit
from app.tool_registry.rate_limit import RateLimiter, rate_limit_key
from app.tool_registry.registry import DatabaseToolRegistry
from app.tool_registry.repository import ToolRegistryRepository
from app.utils.ids import new_trace_id

logger = get_logger("ioc.tool_registry")

_Clock = Callable[[], datetime]


class ToolGateway:
    """所有工具调用的唯一治理执行入口。

    固定顺序：resolve -> 限流 -> 动作确认 -> 执行器绑定 -> BaseTool 执行 -> 审计。
    审计失败只记录高优先级日志，绝不覆盖工具执行结果。
    """

    def __init__(
        self,
        registry: DatabaseToolRegistry,
        executors: ExecutorCatalog,
        rate_limiter: RateLimiter,
        repository_factory: Callable[[], ToolRegistryRepository],
        *,
        confirmation_service: ConfirmationService | None = None,
        clock: _Clock | None = None,
    ) -> None:
        self._registry = registry
        self._executors = executors
        self._rate_limiter = rate_limiter
        self._repository_factory = repository_factory
        self._confirmation_service = confirmation_service
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        capability: str,
        arguments: dict[str, Any],
        context: ToolContext,
        confirmation_token: str | None = None,
        stable_only: bool = False,
    ) -> ToolResult:
        trace_id = self._current_trace_id()
        argument_hash = hash_arguments(arguments)
        summary = build_argument_summary(arguments)

        try:
            resolved = self._registry.resolve(capability, context, stable_only=stable_only)
        except ToolForbiddenError as exc:
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code=exc.code,
                    policy_id=_detail_value(exc, "policy_id"),
                ),
                tool_key=None,
            )
            return self._failure_result(exc.code, exc.message, trace_id=trace_id, detail=exc.detail)
        except CapabilityUnavailableError as exc:
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code=exc.code,
                ),
                tool_key=None,
            )
            return self._failure_result(exc.code, exc.message, trace_id=trace_id, detail=exc.detail)
        except RegistryUnavailableError as exc:
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code=exc.code,
                ),
                tool_key=None,
            )
            return self._failure_result(exc.code, exc.message, trace_id=trace_id, detail=exc.detail)
        except Exception as exc:  # 防御性兜底，避免治理层异常直接泄漏给调用方
            logger.exception(
                "TOOL_GOVERNANCE_FAILED capability=%s",
                capability,
            )
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code="TOOL_REGISTRY_CONFIGURATION_ERROR",
                ),
                tool_key=None,
            )
            return self._failure_result(
                "TOOL_REGISTRY_CONFIGURATION_ERROR",
                "tool governance failed",
                trace_id=trace_id,
                detail={"exception": type(exc).__name__},
            )

        limit = self._rate_limiter.check(
            rate_limit_key(resolved.version_id, context.tenant_id),
            resolved.rate_limit_per_minute,
            self._clock(),
        )
        if not limit.allowed:
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    resolved=resolved,
                    decision="rate_limited",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code="TOOL_RATE_LIMITED",
                ),
                tool_key=resolved.tool_key,
            )
            return self._failure_result(
                "TOOL_RATE_LIMITED",
                "Tool rate limit exceeded",
                trace_id=trace_id,
                detail={"retry_after_seconds": limit.retry_after_seconds},
                resolved=resolved,
            )

        if resolved.action_phase is ActionPhase.COMMIT or resolved.requires_confirmation:
            challenge = self._verify_or_challenge(
                resolved,
                arguments,
                argument_hash,
                summary,
                context,
                confirmation_token,
                trace_id,
            )
            if challenge is not None:
                return challenge

        try:
            tool = self._executors.get(resolved.implementation_ref)
        except ToolNotFoundError as exc:
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    resolved=resolved,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code="TOOL_REGISTRY_CONFIGURATION_ERROR",
                ),
                tool_key=resolved.tool_key,
            )
            return self._failure_result(
                "TOOL_REGISTRY_CONFIGURATION_ERROR",
                f"executor not bound for {resolved.implementation_ref}",
                trace_id=trace_id,
                detail={"implementation_ref": resolved.implementation_ref},
                resolved=resolved,
            )

        audit_id = self._persist_audit(
            self._draft(
                trace_id=trace_id,
                context=context,
                resolved=resolved,
                decision="allowed",
                status="pending",
                argument_hash=argument_hash,
                summary=summary,
            ),
            tool_key=resolved.tool_key,
        )

        started = time.perf_counter()
        result = tool.run(BaseToolInput(context=context, filters=arguments))
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))

        if resolved.action_phase is ActionPhase.PREPARE and not self._has_confirmation_marker(result):
            error_code = "TOOL_REGISTRY_CONFIGURATION_ERROR"
            self._update_audit(
                audit_id,
                tool_key=resolved.tool_key,
                status="failed",
                duration_ms=duration_ms,
                error_code=error_code,
            )
            return self._failure_result(
                error_code,
                "action/prepare tool violated the no-side-effect contract: "
                "missing requires_human_confirmation marker",
                trace_id=trace_id,
                resolved=resolved,
            )

        status = "success" if result.success else "failed"
        error_code = result.error.code if result.error else None
        self._update_audit(
            audit_id,
            tool_key=resolved.tool_key,
            status=status,
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return self._with_governance_metadata(result, resolved, trace_id)

    def _verify_or_challenge(
        self,
        resolved: ResolvedTool,
        arguments: dict[str, Any],
        argument_hash: str,
        summary: dict[str, Any],
        context: ToolContext,
        confirmation_token: str | None,
        trace_id: str,
    ) -> ToolResult | None:
        if self._confirmation_service is None:
            error_code = "TOOL_REGISTRY_CONFIGURATION_ERROR"
            self._persist_audit(
                self._draft(
                    trace_id=trace_id,
                    context=context,
                    resolved=resolved,
                    decision="denied",
                    status="failed",
                    argument_hash=argument_hash,
                    summary=summary,
                    error_code=error_code,
                ),
                tool_key=resolved.tool_key,
            )
            return self._failure_result(
                error_code,
                "confirmation service is not configured",
                trace_id=trace_id,
                resolved=resolved,
            )

        user_id = context.user_id or ""
        if confirmation_token is None:
            return self._challenge_result(
                resolved, argument_hash, summary, context, trace_id, user_id
            )
        try:
            self._confirmation_service.verify(
                confirmation_token,
                trace_id,
                resolved.tool_key,
                resolved.version,
                argument_hash,
                user_id,
                self._clock(),
            )
        except ConfirmationInvalidError:
            return self._challenge_result(
                resolved, argument_hash, summary, context, trace_id, user_id
            )
        return None

    def _challenge_result(
        self,
        resolved: ResolvedTool,
        argument_hash: str,
        summary: dict[str, Any],
        context: ToolContext,
        trace_id: str,
        user_id: str,
    ) -> ToolResult:
        token = self._confirmation_service.issue(
            trace_id,
            resolved.tool_key,
            resolved.version,
            argument_hash,
            user_id,
            self._clock(),
        )
        self._persist_audit(
            self._draft(
                trace_id=trace_id,
                context=context,
                resolved=resolved,
                decision="confirmation_required",
                status="failed",
                argument_hash=argument_hash,
                summary=summary,
                error_code="TOOL_CONFIRMATION_REQUIRED",
            ),
            tool_key=resolved.tool_key,
        )
        return self._failure_result(
            "TOOL_CONFIRMATION_REQUIRED",
            "Action requires human confirmation",
            trace_id=trace_id,
            resolved=resolved,
            extra_metadata={"confirmation_token": token},
        )

    def _current_trace_id(self) -> str:
        trace_id = get_trace_id()
        if not trace_id:
            trace_id = new_trace_id()
        return trace_id

    def _draft(
        self,
        *,
        trace_id: str,
        context: ToolContext,
        decision: str,
        status: str,
        argument_hash: str,
        summary: dict[str, Any],
        resolved: ResolvedTool | None = None,
        error_code: str | None = None,
        policy_id: int | None = None,
    ) -> ToolCallAudit:
        return ToolCallAudit(
            trace_id=trace_id,
            tool_id=resolved.tool_id if resolved else None,
            version_id=resolved.version_id if resolved else None,
            implementation_ref=resolved.implementation_ref if resolved else None,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            role=context.role,
            caller_type=context.caller_type,
            policy_id=policy_id if policy_id is not None else (resolved.policy_id if resolved else None),
            decision=decision,
            gray_bucket=resolved.gray_bucket if resolved else None,
            selected_stable=resolved.selected_stable if resolved else None,
            status=status,
            duration_ms=None,
            error_code=error_code,
            argument_hash=argument_hash,
            argument_summary=summary,
        )

    def _persist_audit(self, audit: ToolCallAudit, *, tool_key: str | None) -> int | None:
        repository = None
        try:
            repository = self._repository_factory()
            created = repository.append_audit(audit)
            repository.db.commit()
            return created.id
        except Exception:
            self._rollback(repository)
            logger.error(
                "TOOL_AUDIT_WRITE_FAILED trace_id=%s tool_key=%s decision=%s",
                audit.trace_id,
                tool_key or "-",
                audit.decision,
            )
            return None
        finally:
            self._close(repository)

    def _update_audit(
        self,
        audit_id: int | None,
        *,
        tool_key: str | None,
        status: str,
        duration_ms: int,
        error_code: str | None,
    ) -> None:
        if audit_id is None:
            return
        repository = None
        try:
            repository = self._repository_factory()
            repository.update_audit(
                audit_id,
                status=status,
                duration_ms=duration_ms,
                error_code=error_code,
            )
            repository.db.commit()
        except Exception:
            self._rollback(repository)
            logger.error(
                "TOOL_AUDIT_UPDATE_FAILED audit_id=%d tool_key=%s status=%s",
                audit_id,
                tool_key or "-",
                status,
            )
        finally:
            self._close(repository)

    @staticmethod
    def _rollback(repository: ToolRegistryRepository | None) -> None:
        if repository is not None:
            try:
                repository.db.rollback()
            except Exception:
                pass

    @staticmethod
    def _close(repository: ToolRegistryRepository | None) -> None:
        if repository is not None:
            try:
                repository.db.close()
            except Exception:
                pass

    @staticmethod
    def _has_confirmation_marker(result: ToolResult) -> bool:
        if isinstance(result.data, dict) and result.data.get("requires_human_confirmation") is True:
            return True
        return result.metadata.get("requires_human_confirmation") is True

    @staticmethod
    def _governance_metadata(resolved: ResolvedTool) -> dict[str, Any]:
        return {
            "tool_key": resolved.tool_key,
            "tool_version": resolved.version,
            "policy_id": resolved.policy_id,
            "gray_bucket": resolved.gray_bucket,
            "selected_stable": resolved.selected_stable,
            "implementation_ref": resolved.implementation_ref,
        }

    @classmethod
    def _with_governance_metadata(
        cls,
        result: ToolResult,
        resolved: ResolvedTool,
        trace_id: str,
    ) -> ToolResult:
        metadata = {**result.metadata, **cls._governance_metadata(resolved)}
        return result.model_copy(update={"metadata": metadata, "trace_id": result.trace_id or trace_id})

    @classmethod
    def _failure_result(
        cls,
        code: str,
        message: str,
        *,
        trace_id: str,
        resolved: ResolvedTool | None = None,
        detail: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        metadata: dict[str, Any] = {}
        if resolved is not None:
            metadata.update(cls._governance_metadata(resolved))
        if extra_metadata:
            metadata.update(extra_metadata)
        return ToolResult(
            success=False,
            data=None,
            evidence=[],
            error=ToolError(code=code, message=message, detail=detail),
            trace_id=trace_id,
            metadata=metadata,
        )


def _detail_value(exc: Exception, key: str) -> Any | None:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return detail.get(key)
    return None
