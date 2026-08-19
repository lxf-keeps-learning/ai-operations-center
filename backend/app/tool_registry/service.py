from __future__ import annotations

from collections.abc import Callable

from jsonschema import SchemaError
from jsonschema.validators import validator_for
from sqlalchemy.orm import Session

from app.tool_center.exceptions import RegistryConfigurationError, ToolNotFoundError
from app.tool_registry.executor_catalog import ExecutorCatalog, executor_catalog
from app.tool_registry.models import ToolCallAudit, ToolDefinition, ToolPolicy, ToolVersion
from app.tool_registry.registry import invalidate_active_registry
from app.tool_registry.repository import AuditFilters, ToolRegistryRepository
from app.tool_registry.schemas import PolicySpec, ToolCreateRequest, ToolUpdateRequest, VersionCreateRequest
from app.utils.timezone import now_local

_ConfigChanged = Callable[[], None]


class ToolRegistryService:
    """事务性管理用例：创建、发布、下线与策略替换。

    每个变更方法独立提交事务；发布时锁定工具定义行，保证稳定/灰度版本不变量
    在并发发布下不被破坏。提交成功后调用 on_config_changed 主动失效 Registry 缓存。
    """

    def __init__(
        self,
        db: Session,
        *,
        executors: ExecutorCatalog | None = None,
        on_config_changed: _ConfigChanged | None = None,
    ) -> None:
        self.db = db
        self.repository = ToolRegistryRepository(db)
        self.executors = executors if executors is not None else executor_catalog
        self._on_config_changed = (
            on_config_changed if on_config_changed is not None else invalidate_active_registry
        )

    # ── 查询 ──────────────────────────────────────────────

    def list_tools(self) -> list[ToolDefinition]:
        return self.repository.list_definitions()

    def list_versions(self, tool_key: str) -> list[ToolVersion]:
        definition = self._get_definition(tool_key)
        return self.repository.list_versions(definition.id)

    def list_audits(
        self,
        filters: AuditFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[ToolCallAudit], int]:
        return self.repository.list_audits(filters, offset, limit)

    # ── 变更 ──────────────────────────────────────────────

    def create_tool(self, request: ToolCreateRequest, operator_id: str) -> ToolDefinition:
        if self.repository.get_definition(request.tool_key) is not None:
            raise RegistryConfigurationError(f"tool_key already exists: {request.tool_key}")
        self._validate_type_phase(request.tool_type, request.action_phase)
        definition = ToolDefinition(
            tool_key=request.tool_key,
            capability=request.capability,
            name=request.name,
            description=request.description,
            tool_type=request.tool_type,
            action_phase=request.action_phase,
            enabled=request.enabled,
        )
        try:
            self.repository.save_definition(definition)
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return definition

    def update_tool(
        self,
        tool_key: str,
        request: ToolUpdateRequest,
        operator_id: str,
    ) -> ToolDefinition:
        definition = self._get_definition(tool_key)
        if request.name is not None:
            definition.name = request.name
        if request.description is not None:
            definition.description = request.description
        if request.enabled is not None:
            definition.enabled = request.enabled
        try:
            self.db.flush()
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return definition

    def create_version(
        self,
        tool_key: str,
        request: VersionCreateRequest,
        operator_id: str,
    ) -> ToolVersion:
        definition = self._get_definition(tool_key)
        if self.repository.get_version(definition.id, request.version) is not None:
            raise RegistryConfigurationError(
                f"version already exists: {tool_key}@{request.version}"
            )
        self._validate_schema(request.input_schema, "input")
        self._validate_schema(request.output_schema, "output")
        version = ToolVersion(
            tool_id=definition.id,
            version=request.version,
            implementation_ref=request.implementation_ref,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
            status="draft",
            is_stable=False,
        )
        try:
            self.repository.save_version(version)
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return version

    def publish_version(
        self,
        tool_key: str,
        version: str,
        *,
        release_type: str,
        gray_percentage: int = 0,
        operator_id: str,
    ) -> ToolVersion:
        definition = self.repository.get_definition(tool_key, for_update=True)
        if definition is None:
            raise ToolNotFoundError(tool_key)
        target = self.repository.get_version(definition.id, version)
        if target is None:
            raise ToolNotFoundError(f"{tool_key}@{version}")
        self._validate_publish(definition, target, release_type, gray_percentage)

        try:
            if release_type == "stable":
                for other in self.repository.list_versions(definition.id):
                    if other.id != target.id and other.status == "published" and other.is_stable:
                        other.status = "retired"
                        other.is_stable = False
                target.status = "published"
                target.is_stable = True
            else:
                for other in self.repository.list_versions(definition.id):
                    if other.id != target.id and other.status == "published" and not other.is_stable:
                        other.status = "retired"
                target.status = "published"
                target.is_stable = False
                self._upsert_gray_policy(definition, target, gray_percentage, operator_id)
            target.published_at = target.published_at or now_local()
            target.published_by = operator_id
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return target

    def retire_version(self, tool_key: str, version: str, operator_id: str) -> ToolVersion:
        definition = self.repository.get_definition(tool_key, for_update=True)
        if definition is None:
            raise ToolNotFoundError(tool_key)
        target = self.repository.get_version(definition.id, version)
        if target is None:
            raise ToolNotFoundError(f"{tool_key}@{version}")
        if target.status != "published":
            raise RegistryConfigurationError("only published versions can be retired")
        try:
            target.status = "retired"
            target.is_stable = False
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return target

    def replace_policies(
        self,
        tool_key: str,
        policies: list[PolicySpec],
        operator_id: str,
    ) -> list[ToolPolicy]:
        definition = self._get_definition(tool_key)
        if definition.action_phase == "commit":
            for spec in policies:
                if not spec.requires_confirmation:
                    raise RegistryConfigurationError(
                        "commit actions always require human confirmation"
                    )

        resolved_specs: list[tuple[PolicySpec, int | None]] = []
        seen_scopes: set[tuple[int | None, str | None, str | None]] = set()
        for spec in policies:
            version_id = None
            if spec.version is not None:
                version_row = self.repository.get_version(definition.id, spec.version)
                if version_row is None:
                    raise RegistryConfigurationError(
                        f"version not found: {tool_key}@{spec.version}"
                    )
                version_id = version_row.id
            scope = (version_id, spec.tenant_id, spec.role)
            if scope in seen_scopes:
                raise RegistryConfigurationError(
                    f"duplicate policy scope: version={spec.version} tenant={spec.tenant_id} role={spec.role}"
                )
            seen_scopes.add(scope)
            resolved_specs.append((spec, version_id))

        try:
            existing = self.repository.list_policies(definition.id)
            for policy in existing:
                self.db.delete(policy)
            created = []
            for spec, version_id in resolved_specs:
                policy = ToolPolicy(
                    tool_id=definition.id,
                    version_id=version_id,
                    tenant_id=spec.tenant_id,
                    role=spec.role,
                    decision=spec.decision,
                    rate_limit_per_minute=spec.rate_limit_per_minute,
                    gray_percentage=spec.gray_percentage,
                    requires_confirmation=spec.requires_confirmation,
                    enabled=spec.enabled,
                    updated_by=operator_id,
                )
                self.repository.save_policy(policy)
                created.append(policy)
            self._commit()
        except Exception:
            self.db.rollback()
            raise
        return created

    # ── 内部 ──────────────────────────────────────────────

    def _get_definition(self, tool_key: str) -> ToolDefinition:
        definition = self.repository.get_definition(tool_key)
        if definition is None:
            raise ToolNotFoundError(tool_key)
        return definition

    def _validate_publish(
        self,
        definition: ToolDefinition,
        target: ToolVersion,
        release_type: str,
        gray_percentage: int,
    ) -> None:
        if not self.executors.contains(target.implementation_ref):
            raise RegistryConfigurationError(
                f"implementation_ref is not bound to an executor: {target.implementation_ref}"
            )
        self._validate_schema(target.input_schema, "input")
        self._validate_schema(target.output_schema, "output")
        self._validate_type_phase(definition.tool_type, definition.action_phase)
        if definition.action_phase == "commit":
            for policy in self.repository.list_policies(definition.id):
                if policy.enabled and not policy.requires_confirmation:
                    raise RegistryConfigurationError(
                        "commit actions always require human confirmation"
                    )
        if release_type == "gray":
            if gray_percentage < 0 or gray_percentage > 100:
                raise RegistryConfigurationError("gray_percentage must be between 0 and 100")
            has_stable = any(
                version.status == "published" and version.is_stable and version.id != target.id
                for version in self.repository.list_versions(definition.id)
            )
            if not has_stable:
                raise RegistryConfigurationError(
                    "a stable version must exist before publishing a gray version"
                )

    def _upsert_gray_policy(
        self,
        definition: ToolDefinition,
        target: ToolVersion,
        gray_percentage: int,
        operator_id: str,
    ) -> None:
        policy = self.repository.get_policy(
            definition.id,
            version_id=target.id,
            tenant_id=None,
            role=None,
        )
        if policy is None:
            policy = ToolPolicy(
                tool_id=definition.id,
                version_id=target.id,
                tenant_id=None,
                role=None,
                decision="allow",
                rate_limit_per_minute=60,
                gray_percentage=gray_percentage,
                requires_confirmation=definition.action_phase == "commit",
                enabled=True,
                updated_by=operator_id,
            )
            self.repository.save_policy(policy)
        else:
            policy.gray_percentage = gray_percentage
            policy.enabled = True
            policy.updated_by = operator_id

    def _commit(self) -> None:
        self.db.commit()
        self._on_config_changed()

    @staticmethod
    def _validate_type_phase(tool_type: str, action_phase: str | None) -> None:
        if tool_type == "action":
            if action_phase not in ("prepare", "commit"):
                raise RegistryConfigurationError(
                    "action tools require action_phase 'prepare' or 'commit'"
                )
        elif action_phase is not None:
            raise RegistryConfigurationError(
                "query/analysis tools must not set action_phase"
            )

    @staticmethod
    def _validate_schema(schema: dict, label: str) -> None:
        try:
            validator_for(schema).check_schema(schema)
        except (SchemaError, TypeError, ValueError) as exc:
            raise RegistryConfigurationError(f"invalid {label} JSON Schema: {exc}") from exc
