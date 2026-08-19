# Tool Registry Minimal Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a MySQL-backed Tool Registry that discovers tools by capability, enforces centralized governance through a single gateway, traces every decision, and preserves the six existing tool flows behind a reversible legacy mode.

**Architecture:** Keep Python `BaseTool` instances in a process-local executor catalog and persist tool identity, versions, policies, and audits in MySQL. A database Registry resolves a capability to a governed version, while `ToolGateway` is the only execution entry point; existing names are translated by a compatibility adapter, and `TOOL_REGISTRY_MODE=legacy` remains the rollback path.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, MySQL/PyMySQL, pytest, FastMCP, `jsonschema`.

**Spec:** `docs/superpowers/specs/2026-08-19-tool-registry-minimal-platform-design.md`

## Global Constraints

- Preserve the fixed Operation Graph business flow; only replace concrete tool names with capability lookups.
- Keep all existing Python tools in process; do not add a remote executor protocol or Registry microservice.
- Persist Registry configuration in MySQL; do not introduce Redis, Celery, or cache-broadcast infrastructure.
- Default configuration cache TTL is 30 seconds; last-known-good query snapshot lifetime is 24 hours.
- Default rate limit is 60 calls per minute for each selected tool version and tenant key.
- Gray rollout uses a fixed SHA-256 algorithm over `tool_key + tenant_id`; calls without `tenant_id` always select stable.
- Only one published stable version and one published gray version may exist per tool.
- `action/prepare` may only create a confirmation draft; `action/commit` must validate a signed confirmation challenge before execution.
- Audit payloads store an argument hash and recursively sanitized summary, never raw secrets.
- Keep `TOOL_REGISTRY_MODE=legacy | database`; initial default is `legacy`.
- New management endpoints are backend-only and administrator-protected; no frontend page is in scope.
- Use the existing virtual environment and run backend commands from `backend/`.
- Preserve the user's unrelated modification in `frontend/src/pages/error-code/IndexPage.vue`.

## File Structure

Create one focused package at `backend/app/tool_registry/`:

- `contracts.py`: enums and immutable runtime DTOs shared by governance, Registry, and Gateway.
- `models.py`: four SQLAlchemy persistence models.
- `executor_catalog.py`: `implementation_ref -> BaseTool` binding only.
- `repository.py`: database reads, writes, row locking, and audit persistence.
- `seed.py`: idempotent definitions for the six built-in tools.
- `policy.py`: deterministic policy precedence and deny/allow resolution.
- `rollout.py`: stable/gray candidate selection and deterministic bucketing.
- `rate_limit.py`: replaceable limiter protocol and in-memory fixed-window implementation.
- `confirmation.py`: signed confirmation challenge issue/verify logic.
- `cache.py`: 30-second configuration cache and 24-hour stable snapshot.
- `registry.py`: capability discovery and resolution orchestration.
- `gateway.py`: the sole governed execution entry and best-effort audit writer.
- `compat.py`: old tool name/capability mapping and legacy/database mode adapter.
- `schemas.py`: management HTTP request/response models.
- `service.py`: transactional management use cases and publish invariants.
- `dependencies.py`: administrator authorization dependency.
- `api.py`: management endpoints and audit search.

Keep `backend/app/tool_center/registry.py` as the legacy rollback implementation. Modify `backend/app/tools/register.py` to populate both the legacy Registry and the new executor catalog without connecting to MySQL at import time.

---

### Task 1: Runtime contracts, configuration, and executor catalog

**Files:**
- Create: `backend/app/tool_registry/__init__.py`
- Create: `backend/app/tool_registry/contracts.py`
- Create: `backend/app/tool_registry/executor_catalog.py`
- Modify: `backend/app/tool_center/contracts.py`
- Modify: `backend/app/config/settings.py`
- Modify: `backend/app/core/config/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/tool_registry/test_contracts.py`
- Test: `backend/tests/tool_registry/test_executor_catalog.py`

**Interfaces:**
- Produces: `ToolType`, `ActionPhase`, `VersionStatus`, `GovernanceDecision`, `ToolDefinitionRecord`, `ToolVersionRecord`, `ToolPolicyRecord`, `ToolDescriptor`, `RegistrySnapshot`, `ResolvedTool`.
- Produces: `ExecutorCatalog.register(ref: str, tool: BaseTool)`, `get(ref: str)`, `contains(ref: str)`, `clear()`.
- Produces: `ToolContext.caller_type: Literal["internal", "external"]` with safe default `external`.

- [ ] **Step 1: Write failing contract and executor tests**

```python
def test_tool_context_defaults_to_external() -> None:
    assert ToolContext().caller_type == "external"

def test_executor_catalog_binds_by_implementation_ref() -> None:
    catalog = ExecutorCatalog()
    tool = StubTool()
    catalog.register("builtin.stub", tool)
    assert catalog.get("builtin.stub") is tool

def test_executor_catalog_rejects_empty_ref() -> None:
    with pytest.raises(ValueError, match="implementation_ref"):
        ExecutorCatalog().register("", StubTool())
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_contracts.py tests/tool_registry/test_executor_catalog.py -q`

Expected: collection fails because `app.tool_registry` and `ToolContext.caller_type` do not exist.

- [ ] **Step 3: Add exact contracts and catalog behavior**

```python
class ToolType(StrEnum):
    QUERY = "query"
    ANALYSIS = "analysis"
    ACTION = "action"

class ActionPhase(StrEnum):
    PREPARE = "prepare"
    COMMIT = "commit"

@dataclass(frozen=True)
class RegistrySnapshot:
    revision: str
    loaded_at: datetime
    definitions: tuple[ToolDefinitionRecord, ...]
    versions: tuple[ToolVersionRecord, ...]
    policies: tuple[ToolPolicyRecord, ...]

@dataclass(frozen=True)
class ResolvedTool:
    tool_id: int
    tool_key: str
    capability: str
    tool_type: ToolType
    action_phase: ActionPhase | None
    version_id: int
    version: str
    implementation_ref: str
    policy_id: int | None
    rate_limit_per_minute: int
    gray_bucket: int | None
    selected_stable: bool
```

Implement `ExecutorCatalog` with duplicate replacement semantics matching the current test-friendly legacy Registry. `get()` raises `ToolNotFoundError(ref)`.

- [ ] **Step 4: Add exact settings and dependency**

```python
tool_registry_mode: Literal["legacy", "database"] = "legacy"
tool_registry_cache_ttl_seconds: int = Field(default=30, ge=1)
tool_registry_stale_query_ttl_seconds: int = Field(default=86400, ge=30)
tool_default_rate_limit_per_minute: int = Field(default=60, ge=1)
tool_confirmation_ttl_seconds: int = Field(default=300, ge=30)
tool_confirmation_secret: str = ""
```

Expose the same values through `AppSettings`, document them in `.env.example`, and add `jsonschema>=4.23.0,<5.0.0` to runtime dependencies.

- [ ] **Step 5: Run focused tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_contracts.py tests/tool_registry/test_executor_catalog.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry backend/app/tool_center/contracts.py backend/app/config/settings.py backend/app/core/config/settings.py backend/.env.example backend/pyproject.toml backend/tests/tool_registry
git commit -m "feat: add tool registry runtime contracts"
```

### Task 2: Persistence models and Alembic migration

**Files:**
- Create: `backend/app/tool_registry/models.py`
- Create: `backend/alembic/versions/20260819_0004_create_tool_registry_tables.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/tool_registry/test_models.py`
- Test: `backend/tests/tool_registry/test_migration.py`

**Interfaces:**
- Consumes: enums from Task 1 as string values at persistence boundaries.
- Produces: `ToolDefinition`, `ToolVersion`, `ToolPolicy`, `ToolCallAudit`.

- [ ] **Step 1: Write failing model tests with an isolated SQLite database**

```python
def test_tool_definition_and_version_constraints(session: Session) -> None:
    tool = ToolDefinition(
        tool_key="kpi_query", capability="query.kpi", name="KPI",
        description="desc", tool_type="query", action_phase=None, enabled=True,
    )
    session.add(tool)
    session.flush()
    session.add(ToolVersion(
        tool_id=tool.id, version="1.0.0", implementation_ref="builtin.kpi_query",
        input_schema={"type": "object"}, output_schema={"type": "object"},
        status="published", is_stable=True,
    ))
    session.commit()
    assert session.scalar(select(ToolDefinition).where(ToolDefinition.capability == "query.kpi")) is tool
```

Also assert `(tool_id, version)` uniqueness, nullable audit `tool_id/version_id`, policy indexes, and cascade behavior.

- [ ] **Step 2: Run tests and verify missing models**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_models.py -q`

Expected: FAIL importing `app.tool_registry.models`.

- [ ] **Step 3: Implement the four ORM models**

Use SQLAlchemy 2 `Mapped` fields, `now_local`, explicit `ForeignKey`, and these table names:

```python
class ToolDefinition(Base):
    __tablename__ = "tool_definitions"

class ToolVersion(Base):
    __tablename__ = "tool_versions"
    __table_args__ = (UniqueConstraint("tool_id", "version", name="uk_tool_version"),)

class ToolPolicy(Base):
    __tablename__ = "tool_policies"

class ToolCallAudit(Base):
    __tablename__ = "tool_call_audits"
```

Map every field from Spec sections 4.1-4.4, including `action_phase`, `gray_bucket`, `argument_hash`, sanitized `argument_summary` JSON, and operator timestamps.

- [ ] **Step 4: Write the migration and metadata import**

Set `revision = "20260819_0004"` and `down_revision = "20260806_0003"`. Create all foreign keys and indexes in `upgrade()` and drop them in reverse order in `downgrade()`. Import all four models in `alembic/env.py` so autogeneration sees them.

- [ ] **Step 5: Verify schema creation and migration graph**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_models.py tests/tool_registry/test_migration.py -q`

Run: `.venv/bin/alembic heads`

Expected: tests PASS and the only head is `20260819_0004`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tool_registry/models.py backend/alembic backend/tests/tool_registry/test_models.py backend/tests/tool_registry/test_migration.py
git commit -m "feat: persist tool registry metadata"
```

### Task 3: Repository and idempotent built-in seed

**Files:**
- Create: `backend/app/tool_registry/repository.py`
- Create: `backend/app/tool_registry/seed.py`
- Create: `backend/scripts/seed_tool_registry.py`
- Modify: `backend/app/tools/register.py`
- Test: `backend/tests/tool_registry/test_repository.py`
- Test: `backend/tests/tool_registry/test_seed.py`

**Interfaces:**
- Produces: `ToolRegistryRepository.load_snapshot() -> RegistrySnapshot`.
- Produces: management CRUD and `append_audit(audit: ToolCallAudit) -> None`.
- Produces: `seed_builtin_tools(db: Session, operator_id: str = "system") -> None`.
- Produces: process-global `executor_catalog` populated by `register_all_tools()`.

- [ ] **Step 1: Write failing repository and seed tests**

```python
def test_seed_builtin_tools_is_idempotent(session: Session) -> None:
    seed_builtin_tools(session)
    seed_builtin_tools(session)
    assert session.scalar(select(func.count()).select_from(ToolDefinition)) == 6
    assert session.scalar(select(func.count()).select_from(ToolVersion)) == 6

def test_seed_marks_draft_tool_as_action_prepare(session: Session) -> None:
    seed_builtin_tools(session)
    tool = session.scalar(select(ToolDefinition).where(ToolDefinition.tool_key == "work_order_draft"))
    assert tool.tool_type == "action"
    assert tool.action_phase == "prepare"
```

Assert all six versions are `1.0.0`, `published`, stable, use the exact `builtin.kpi_query` through `builtin.work_order_draft` references listed in `BUILTIN_TOOLS`, and receive an enabled default allow policy with rate limit 60.

- [ ] **Step 2: Run tests and verify failure**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_repository.py tests/tool_registry/test_seed.py -q`

Expected: FAIL because repository and seed modules do not exist.

- [ ] **Step 3: Implement repository read/write boundaries**

```python
class ToolRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_definition(self, tool_key: str, *, for_update: bool = False) -> ToolDefinition | None:
        statement = select(ToolDefinition).where(ToolDefinition.tool_key == tool_key)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)
```

Also implement these exact signatures: `load_snapshot() -> RegistrySnapshot`, `list_audits(filters: AuditFilters, offset: int, limit: int) -> tuple[list[ToolCallAudit], int]`, `append_audit(audit: ToolCallAudit) -> ToolCallAudit`, and `update_audit(audit_id: int, *, status: str, duration_ms: int, error_code: str | None) -> None`. `load_snapshot()` must eager-load enabled definitions, published versions, and enabled policies in bounded queries; it must convert them to immutable records before the session closes.

- [ ] **Step 4: Implement the exact built-in mapping and executor bindings**

```python
BUILTIN_TOOLS = (
    BuiltinTool("kpi_query", "query.kpi", "query", None, "builtin.kpi_query"),
    BuiltinTool("alarm_query", "query.alarm", "query", None, "builtin.alarm_query"),
    BuiltinTool("risk_query", "query.risk", "query", None, "builtin.risk_query"),
    BuiltinTool("work_order_query", "query.work_order", "query", None, "builtin.work_order_query"),
    BuiltinTool("ioc_summary_analysis", "analysis.ioc_summary", "analysis", None, "builtin.ioc_summary_analysis"),
    BuiltinTool("work_order_draft", "action.work_order.draft", "action", "prepare", "builtin.work_order_draft"),
)
```

Keep the existing `registry.register(tool)` calls and add matching `executor_catalog.register(ref, tool)` calls using the same instances.

- [ ] **Step 5: Add the explicit seed command, run tests, and commit**

The script opens `get_session_local()()`, calls `seed_builtin_tools`, rolls back on exception, closes the session, and exits non-zero on failure. Do not seed from module import or FastAPI startup.

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_repository.py tests/tool_registry/test_seed.py tests/tools/test_tool_registry_integration.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry/repository.py backend/app/tool_registry/seed.py backend/app/tools/register.py backend/scripts/seed_tool_registry.py backend/tests/tool_registry
git commit -m "feat: seed built-in tool registry entries"
```

### Task 4: Pure governance components

**Files:**
- Create: `backend/app/tool_registry/policy.py`
- Create: `backend/app/tool_registry/rollout.py`
- Create: `backend/app/tool_registry/rate_limit.py`
- Create: `backend/app/tool_registry/confirmation.py`
- Test: `backend/tests/tool_registry/test_policy.py`
- Test: `backend/tests/tool_registry/test_rollout.py`
- Test: `backend/tests/tool_registry/test_rate_limit.py`
- Test: `backend/tests/tool_registry/test_confirmation.py`

**Interfaces:**
- Produces: `resolve_policy(policies, version_id, context) -> EffectivePolicy`.
- Produces: `gray_bucket(tool_key: str, tenant_id: str) -> int` and `choose_version(tool: ToolDefinitionRecord, versions: Sequence[ToolVersionRecord], policies: Sequence[ToolPolicyRecord], context: ToolContext, stable_only: bool = False) -> VersionSelection`.
- Produces: `RateLimiter.check(key: str, limit: int, now: datetime) -> RateLimitDecision`.
- Produces: `ConfirmationService.issue(trace_id: str, tool_key: str, version: str, argument_hash: str, user_id: str, now: datetime) -> str` and `verify(token: str, trace_id: str, tool_key: str, version: str, argument_hash: str, user_id: str, now: datetime) -> None`.

- [ ] **Step 1: Write failing policy and rollout tests**

```python
def test_version_tenant_role_policy_wins() -> None:
    result = resolve_policy(POLICIES, version_id=12, context=ToolContext(tenant_id="t1", role="operator"))
    assert result.policy_id == 4

def test_gray_bucket_is_stable() -> None:
    assert gray_bucket("kpi_query", "tenant-a") == gray_bucket("kpi_query", "tenant-a")
    assert 0 <= gray_bucket("kpi_query", "tenant-a") <= 99

def test_missing_tenant_always_selects_stable() -> None:
    assert choose_version(STABLE, GRAY, ToolContext(), gray_percentage=100).id == STABLE.id
```

- [ ] **Step 2: Write failing limiter and confirmation tests**

```python
def test_fixed_window_blocks_sixty_first_call() -> None:
    limiter = InMemoryFixedWindowRateLimiter()
    now = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    assert all(limiter.check("v1:t1", 60, now).allowed for _ in range(60))
    denied = limiter.check("v1:t1", 60, now)
    assert denied.allowed is False
    assert denied.retry_after_seconds == 60

def test_confirmation_rejects_argument_tampering() -> None:
    token = service.issue("trace-1", "wo_commit", "1.0.0", hash_args({"id": 1}), "u1", now)
    with pytest.raises(ConfirmationInvalidError):
        service.verify(token, "trace-1", "wo_commit", "1.0.0", hash_args({"id": 2}), "u1", now)
```

- [ ] **Step 3: Implement deterministic policy, rollout, and fixed-window behavior**

Policy precedence must exactly follow the spec. A matching `deny` is final at that specificity. `gray_bucket` must be:

```python
digest = hashlib.sha256(f"tool-registry-v1:{tool_key}:{tenant_id}".encode()).digest()
return int.from_bytes(digest[:8], "big") % 100
```

The limiter key is `f"{version_id}:{tenant_id or '__internal__'}"`; calculate retry time from the next UTC minute boundary and guard state with `threading.Lock`.

- [ ] **Step 4: Implement signed confirmation challenges**

Serialize a compact JSON payload containing `trace_id`, `tool_key`, `version`, `argument_hash`, `user_id`, `issued_at`, and `expires_at`. Sign it with HMAC-SHA256 and URL-safe base64. Use `hmac.compare_digest`; reject empty secrets, signature mismatch, expired tokens, and any field mismatch.

- [ ] **Step 5: Run focused tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_policy.py tests/tool_registry/test_rollout.py tests/tool_registry/test_rate_limit.py tests/tool_registry/test_confirmation.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry/policy.py backend/app/tool_registry/rollout.py backend/app/tool_registry/rate_limit.py backend/app/tool_registry/confirmation.py backend/tests/tool_registry
git commit -m "feat: enforce tool governance policies"
```

### Task 5: Registry cache, discovery, and capability resolution

**Files:**
- Create: `backend/app/tool_registry/cache.py`
- Create: `backend/app/tool_registry/registry.py`
- Modify: `backend/app/tool_center/exceptions.py`
- Test: `backend/tests/tool_registry/test_cache.py`
- Test: `backend/tests/tool_registry/test_database_registry.py`

**Interfaces:**
- Consumes: `ToolRegistryRepository.load_snapshot`, policy and rollout functions.
- Produces: `RegistryCache.get_or_load(loader)`, `invalidate()`, `get_stable_fallback(now)`.
- Produces: `DatabaseToolRegistry.discover(context, capability=None) -> list[ToolDescriptor]`.
- Produces: `DatabaseToolRegistry.resolve(capability, context, stable_only=False) -> ResolvedTool`.

- [ ] **Step 1: Write failing cache behavior tests using an injected clock**

```python
def test_cache_refreshes_after_thirty_seconds() -> None:
    cache = RegistryCache(ttl_seconds=30, stale_query_ttl_seconds=86400, clock=clock)
    assert cache.get_or_load(loader).revision == "r1"
    clock.advance(seconds=31)
    assert cache.get_or_load(loader).revision == "r2"

def test_stale_snapshot_expires_after_twenty_four_hours() -> None:
    cache.get_or_load(loader)
    clock.advance(seconds=86401)
    with pytest.raises(RegistryUnavailableError):
        cache.get_stable_fallback(clock.now())
```

- [ ] **Step 2: Write failing discovery and resolution tests**

Cover disabled tools, draft exclusion, no stable version, gray hit/miss, no-tenant stable selection, policy denial, version policy override, `stable_only=True`, and unavailable database fallback.

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_cache.py tests/tool_registry/test_database_registry.py -q`

Expected: FAIL because cache and database Registry do not exist.

- [ ] **Step 3: Implement cache and explicit tool exceptions**

Add `CapabilityUnavailableError`, `ToolForbiddenError`, `ToolRateLimitedError`, `ConfirmationRequiredError`, `RegistryConfigurationError`, and `RegistryUnavailableError` with stable string codes. Cache immutable snapshots only; never retain SQLAlchemy sessions or ORM instances.

- [ ] **Step 4: Implement `DatabaseToolRegistry` resolution**

```python
class DatabaseToolRegistry:
    def invalidate(self) -> None:
        self.cache.invalidate()
```

Implement the exact additional signatures `discover(context: ToolContext, capability: str | None = None) -> list[ToolDescriptor]` and `resolve(capability: str, context: ToolContext, *, stable_only: bool = False) -> ResolvedTool`. On database load failure: use valid normal cache first; allow stale stable snapshot only for query/analysis resolution, force `stable_only`, and reject every action type. Log fallback with capability and snapshot age.

- [ ] **Step 5: Run tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_cache.py tests/tool_registry/test_database_registry.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry/cache.py backend/app/tool_registry/registry.py backend/app/tool_center/exceptions.py backend/tests/tool_registry
git commit -m "feat: resolve governed tool capabilities"
```

### Task 6: Tool Gateway, auditing, and confirmation flow

**Files:**
- Create: `backend/app/tool_registry/gateway.py`
- Modify: `backend/app/tool_center/telemetry.py`
- Test: `backend/tests/tool_registry/test_gateway.py`
- Test: `backend/tests/tool_registry/test_audit.py`

**Interfaces:**
- Consumes: `DatabaseToolRegistry`, `ExecutorCatalog`, `RateLimiter`, `ConfirmationService`, repository factory.
- Produces: `ToolGateway.execute(capability, arguments, context, confirmation_token=None, stable_only=False) -> ToolResult`.
- Produces: governance metadata keys `tool_key`, `tool_version`, `policy_id`, `gray_bucket`, `selected_stable`, `implementation_ref`.

- [ ] **Step 1: Write failing gateway decision tests**

```python
def test_gateway_executes_selected_executor_and_enriches_metadata() -> None:
    result = gateway.execute("query.kpi", {"department": "安全环保部"}, INTERNAL_CONTEXT)
    assert result.success is True
    assert result.metadata["tool_version"] == "1.0.0"
    assert result.metadata["implementation_ref"] == "builtin.kpi_query"

def test_commit_without_confirmation_returns_challenge() -> None:
    result = gateway.execute("action.work_order.commit", {"draft_id": "d1"}, INTERNAL_CONTEXT)
    assert result.success is False
    assert result.error.code == "TOOL_CONFIRMATION_REQUIRED"
    assert result.metadata["confirmation_token"]

def test_prepare_action_executes_without_preconfirmation() -> None:
    result = gateway.execute("action.work_order.draft", DRAFT_ARGS, INTERNAL_CONTEXT)
    assert result.success is True
    assert result.data["requires_human_confirmation"] is True
```

- [ ] **Step 2: Write failing audit tests**

Assert allowed, denied, rate-limited, confirmation-required, success, and tool-failure decisions. Verify `argument_hash` changes with arguments, sensitive keys become `***`, and audit write failure logs an error but does not replace a successful tool result.

- [ ] **Step 3: Implement Gateway in fixed order**

```python
def execute(
    self,
    capability: str,
    arguments: dict[str, Any],
    context: ToolContext,
    confirmation_token: str | None = None,
    stable_only: bool = False,
) -> ToolResult:
    resolved = self.registry.resolve(capability, context, stable_only=stable_only)
    limit = self.rate_limiter.check(rate_key(resolved, context), resolved.rate_limit_per_minute, self.clock())
    if not limit.allowed:
        return self._rejected_result("TOOL_RATE_LIMITED", retry_after=limit.retry_after_seconds)
    if resolved.action_phase is ActionPhase.COMMIT:
        return self._verify_or_challenge(resolved, arguments, context, confirmation_token)
    tool = self.executors.get(resolved.implementation_ref)
    result = tool.run(BaseToolInput(context=context, filters=arguments))
    return self._with_governance_metadata(result, resolved)
```

Create the audit row before returning every decision, then update status/duration after execution. If persistence fails, emit an error log containing `trace_id`, `tool_key`, and decision; do not log the raw arguments.

After an `action/prepare` executor returns, require `result.data["requires_human_confirmation"] is True` or `result.metadata["requires_human_confirmation"] is True`. If neither marker is present, replace the result with `TOOL_CONFIGURATION_ERROR` and audit the contract violation; this makes the no-side-effect preparation contract visible and testable.

- [ ] **Step 4: Run tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_gateway.py tests/tool_registry/test_audit.py tests/tool_center/test_base_tool.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry/gateway.py backend/app/tool_center/telemetry.py backend/tests/tool_registry
git commit -m "feat: route tool execution through governance gateway"
```

### Task 7: Transactional management service and administrator API

**Files:**
- Create: `backend/app/tool_registry/schemas.py`
- Create: `backend/app/tool_registry/service.py`
- Create: `backend/app/tool_registry/dependencies.py`
- Create: `backend/app/tool_registry/api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/exception/error_code.py`
- Test: `backend/tests/tool_registry/test_management_service.py`
- Test: `backend/tests/tool_registry/test_management_api.py`

**Interfaces:**
- Produces: CRUD, publish, retire, policy replace, and audit list service functions.
- Produces: `require_tool_registry_admin() -> UserContext`.
- Produces: `/api/v1/tool-registry/*` endpoints from Spec section 7.

- [ ] **Step 1: Write failing service invariant tests**

```python
def test_publish_rejects_unbound_executor(service) -> None:
    with pytest.raises(RegistryConfigurationError, match="implementation_ref"):
        service.publish_version("new_tool", "1.0.0", release_type="stable", operator_id="admin")

def test_publish_gray_requires_stable(service) -> None:
    with pytest.raises(RegistryConfigurationError, match="stable"):
        service.publish_version("new_tool", "1.1.0", release_type="gray", operator_id="admin")

def test_commit_action_cannot_disable_confirmation(service) -> None:
    with pytest.raises(RegistryConfigurationError, match="confirmation"):
        service.replace_policies("commit_tool", [POLICY_WITH_CONFIRMATION_FALSE], "admin")
```

Also test valid JSON Schema via `validator_for(schema).check_schema(schema)`, one stable/gray invariant, row locking, retirement, and cache invalidation after commit.

- [ ] **Step 2: Write failing API authorization and contract tests**

Use `X-Roles: admin` for success. Assert missing admin returns 403 for every mutation and audit list, create returns 200 standard `ApiResponse`, publish validates release type, and filters paginate audits.

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_management_service.py tests/tool_registry/test_management_api.py -q`

Expected: FAIL because management service and router do not exist.

- [ ] **Step 3: Implement service transactions and exact authorization**

```python
def require_tool_registry_admin() -> UserContext:
    user = get_user_context()
    if "admin" not in user.roles:
        raise AppException.from_error_code(FORBIDDEN)
    return user
```

For publish, lock the definition row using `select(ToolDefinition).where(ToolDefinition.tool_key == tool_key).with_for_update()`, validate executor and schemas, change stable/gray flags atomically, commit once, then invalidate Registry cache. Roll back on any error.

- [ ] **Step 4: Implement and mount all management endpoints**

Use prefix `/tool-registry`, `Depends(get_db)`, and the admin dependency for:

```text
GET    /tools
POST   /tools
PATCH  /tools/{tool_key}
POST   /tools/{tool_key}/versions
POST   /tools/{tool_key}/versions/{version}/publish
POST   /tools/{tool_key}/versions/{version}/retire
PUT    /tools/{tool_key}/policies
GET    /audits
```

Return the existing `ApiResponse` envelope. Add dedicated Registry business error codes without changing existing numeric codes.

- [ ] **Step 5: Run tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_management_service.py tests/tool_registry/test_management_api.py tests/test_api.py -q`

Expected: PASS.

```bash
git add backend/app/tool_registry backend/app/main.py backend/app/core/exception/error_code.py backend/tests/tool_registry
git commit -m "feat: add tool registry management api"
```

### Task 8: Legacy/database compatibility adapter and existing Tool API

**Files:**
- Create: `backend/app/tool_registry/compat.py`
- Modify: `backend/app/tools/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/tool_registry/test_compat.py`
- Modify: `backend/tests/tools/test_tools_api.py`

**Interfaces:**
- Produces: `LEGACY_NAME_TO_CAPABILITY` and reverse mapping.
- Produces: `execute_tool(name_or_capability, arguments, context, confirmation_token=None, stable_only=False) -> ToolResult`.
- Produces: `discover_tools(context) -> list[ToolDescriptor]`.

- [ ] **Step 1: Write failing mode and compatibility tests**

```python
def test_legacy_mode_uses_current_registry(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")
    assert execute_tool("kpi_query", {}, INTERNAL_CONTEXT).success is True

def test_database_mode_translates_legacy_name(monkeypatch, fake_gateway) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    execute_tool("kpi_query", {}, INTERNAL_CONTEXT)
    fake_gateway.execute.assert_called_once_with("query.kpi", {}, INTERNAL_CONTEXT, confirmation_token=None, stable_only=False)
```

- [ ] **Step 2: Implement lazy runtime construction**

Do not connect to MySQL at import time. Construct `DatabaseToolRegistry` and `ToolGateway` lazily from `get_session_local`, process settings, executor catalog, limiter, and confirmation service. Expose `reset_runtime_for_tests()` to clear cached singletons.

- [ ] **Step 3: Route the existing HTTP Tool API through the adapter**

Keep request compatibility with `tool_name`, `filters`, and `params`; add optional `confirmation_token` and `stable_only`. For HTTP calls, always derive `user_id`, `tenant_id`, and `role` from middleware `UserContext`; use `org_id` as `tenant_id` and the first declared role as the single policy role. Ignore body-supplied identity fields so callers cannot spoof a tenant or role. Only locale and business filters may come from the body. In database mode map governance errors to 403, 429, 404, or 503 while keeping the standard response envelope. A confirmed retry must reuse the challenge request's `X-Trace-Id`, because the signed challenge binds the trace, arguments, user, tool, and version.

- [ ] **Step 4: Run both mode suites and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_compat.py tests/tools/test_tools_api.py tests/tools/test_tool_center_integration.py -q`

Expected: PASS in legacy tests and injected database-mode tests.

```bash
git add backend/app/tool_registry/compat.py backend/app/tools/api.py backend/app/main.py backend/tests/tool_registry/test_compat.py backend/tests/tools/test_tools_api.py
git commit -m "feat: add reversible tool registry runtime mode"
```

### Task 9: Operation Graph capability migration

**Files:**
- Modify: `backend/app/operation_agent/nodes/query_operation_data_node.py`
- Modify: `backend/tests/operation_agent/test_operation_graph.py`
- Create: `backend/tests/tool_registry/test_operation_graph_gateway.py`

**Interfaces:**
- Consumes: `execute_tool(capability, arguments, context)` from Task 8.
- Preserves: `OperationState`, raw data, evidence, errors, metrics, and fixed six-node ordering.

- [ ] **Step 1: Write a failing test proving the Graph requests capabilities**

```python
def test_query_node_uses_capabilities(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(node_module, "execute_tool", lambda capability, *_args, **_kw: capture(calls, capability))
    node_module.query_operation_data_node(SAFETY_STATE)
    assert calls == [
        "query.kpi", "query.alarm", "query.risk", "query.work_order", "analysis.ioc_summary",
    ]
```

- [ ] **Step 2: Replace concrete names with fixed business capabilities**

```python
_QUERY_CAPABILITIES = {
    "kpi": "query.kpi",
    "alarm": "query.alarm",
    "risk": "query.risk",
    "work_order": "query.work_order",
}
_SUMMARY_CAPABILITY = "analysis.ioc_summary"
```

Set `caller_type="internal"` in `_tool_context`. Preserve evidence labels with the selected `tool_key` from result metadata so downstream report content does not change.

- [ ] **Step 3: Run Graph tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_operation_graph_gateway.py tests/operation_agent/test_operation_graph.py -q`

Expected: PASS with unchanged graph node order and state contract.

```bash
git add backend/app/operation_agent/nodes/query_operation_data_node.py backend/tests/operation_agent/test_operation_graph.py backend/tests/tool_registry/test_operation_graph_gateway.py
git commit -m "refactor: resolve operation tools by capability"
```

### Task 10: MCP discovery and governed execution

**Files:**
- Modify: `backend/app/mcp_adapter/tools.py`
- Modify: `backend/app/mcp_adapter/server.py`
- Create: `backend/tests/tool_registry/test_mcp_registry.py`

**Interfaces:**
- Consumes: `discover_tools` and `execute_tool` from Task 8.
- Preserves: public MCP names `ioc_query_kpi`, `ioc_query_alarms`, `ioc_query_risks`, `ioc_query_work_orders`, `ioc_analyze_summary`.

- [ ] **Step 1: Write failing MCP adapter tests**

```python
def test_mcp_query_executes_capability(monkeypatch) -> None:
    monkeypatch.setattr(adapter, "execute_tool", fake_execute)
    adapter.execute_query_tool("query.kpi", {"department": "安全环保部"})
    assert fake_execute.call_args.args[0] == "query.kpi"
    assert fake_execute.call_args.args[2].caller_type == "internal"

def test_mcp_description_comes_from_registry(monkeypatch) -> None:
    monkeypatch.setattr(server, "discover_tools", lambda *_: [KPI_DESCRIPTOR])
    mcp = server.build_mcp_server()
    assert registered_description(mcp, "ioc_query_kpi") == KPI_DESCRIPTOR.description
```

- [ ] **Step 2: Rebuild MCP registration from Registry descriptors**

Keep a compatibility map only for stable public MCP name to capability. `build_mcp_server()` discovers those capabilities, applies current Registry descriptions and input schemas, and registers callables that invoke `execute_tool`. If database discovery is unavailable during process construction, fail application startup in database mode rather than silently exposing ungoverned tools; legacy mode uses existing tool descriptions.

- [ ] **Step 3: Run MCP tests and commit**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry/test_mcp_registry.py tests/tools/test_tool_registry_integration.py -q`

Expected: PASS and public MCP names remain unchanged.

```bash
git add backend/app/mcp_adapter backend/tests/tool_registry/test_mcp_registry.py
git commit -m "feat: govern mcp tools through registry"
```

### Task 11: End-to-end migration, failure tests, and operator documentation

**Files:**
- Create: `backend/tests/tool_registry/test_database_mode_integration.py`
- Create: `backend/tests/tool_registry/test_failure_modes.py`
- Modify: `backend/README.md`
- Modify: `docs/数据库初始化说明.md`
- Modify: `docs/HTTP状态码与业务错误码说明.md`

**Interfaces:**
- Verifies every acceptance criterion in Spec section 10.
- Documents migration, seed, mode switch, rollback, cache limits, and single-instance limiter semantics.

- [ ] **Step 1: Write end-to-end database-mode tests**

Create a SQLite `StaticPool` session factory, create the four Registry tables, seed built-ins, register executors, inject the factory, and set database mode. Assert:

```python
assert execute_tool("kpi_query", {}, INTERNAL_CONTEXT).metadata["tool_version"] == "1.0.0"
assert execute_tool("query.kpi", {}, INTERNAL_CONTEXT).success is True
assert audit_count(session_factory) == 2
assert execute_tool("action.work_order.draft", DRAFT_ARGS, INTERNAL_CONTEXT).success is True
```

Also verify publish gray -> stable tenant hashing, retire gray -> stable fallback, permission denial, rate limit 61st call, and `legacy` rollback.

- [ ] **Step 2: Write dependency-failure and security tests**

Cover MySQL load failure with fresh cache, stale query snapshot under 24 hours, expired snapshot, every action rejected on stale data, audit write failure, missing executor, non-admin management access, cross-tenant policy isolation, confirmation expiry, and argument tampering.

- [ ] **Step 3: Run the complete focused Registry and caller suite**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/tool_registry tests/tool_center tests/tools tests/operation_agent -q`

Expected: PASS.

- [ ] **Step 4: Document exact rollout and rollback commands**

Document:

```bash
cd backend
.venv/bin/alembic upgrade head
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/seed_tool_registry.py
# verify management API and audit records, then set:
TOOL_REGISTRY_MODE=database
# rollback without data loss:
TOOL_REGISTRY_MODE=legacy
```

State explicitly that the default limiter is per process and that production multi-worker global quotas require a future Redis implementation.

- [ ] **Step 5: Run compile, migration, and full backend verification**

Run: `.venv/bin/python -m compileall app/tool_registry app/tool_center app/tools app/mcp_adapter app/operation_agent`

Run: `.venv/bin/alembic heads`

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`

Expected: compilation succeeds, Alembic reports only `20260819_0004`, and the backend suite passes. If unrelated baseline failures remain, capture both the baseline and post-change outputs and prove this feature adds no new failures before proceeding.

- [ ] **Step 6: Commit documentation and end-to-end verification assets**

```bash
git add backend/tests/tool_registry backend/README.md docs/数据库初始化说明.md docs/HTTP状态码与业务错误码说明.md
git commit -m "test: verify tool registry platform rollout"
```

### Task 12: Final review and branch handoff

**Files:**
- Review: all files changed by Tasks 1-11
- Review: `docs/superpowers/specs/2026-08-19-tool-registry-minimal-platform-design.md`
- Review: `docs/superpowers/plans/2026-08-19-tool-registry-minimal-platform.md`

**Interfaces:**
- Confirms implementation matches the approved spec and keeps rollback intact.

- [ ] **Step 1: Inspect the final diff for bypasses and unrelated changes**

Run: `git diff --check 0c949c1 HEAD`

Run: `rg -n "get_tool\(|\.run\(" backend/app/operation_agent backend/app/mcp_adapter backend/app/tools/api.py`

Expected: no direct governed caller bypass remains; legacy calls exist only inside `tool_registry/compat.py` and legacy tests.

- [ ] **Step 2: Verify configuration and security invariants**

Run: `rg -n "TOOL_CONFIRMATION_SECRET|tool_confirmation_secret|argument_summary|sanitize_for_trace" backend/app backend/.env.example`

Expected: no real secret is committed, audit summaries use sanitization, and commit-action verification rejects an empty secret.

- [ ] **Step 3: Record final verification evidence and request code review**

Record exact commands, pass/fail counts, migration head, known baseline failures if any, and the commit range. Use `superpowers:requesting-code-review`; resolve all high-confidence findings before integration.

- [ ] **Step 4: Present integration options**

Use `superpowers:finishing-a-development-branch` only after focused and full verification evidence is current. Do not merge, rebase, or delete a worktree without the user's explicit choice.
