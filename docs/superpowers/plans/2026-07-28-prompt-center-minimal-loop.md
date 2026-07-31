# Prompt Center Minimal Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有配置中心交付 5 个真实 Prompt 的编辑、测试、审核、发布、回滚和 LangSmith `push_prompt`/Trace 观测闭环。

**Architecture:** IOC 数据库保存不可变 Prompt 版本和 production 发布指针；5 个真实 Graph 节点通过统一 `PromptResolver` 读取发布版本，异常时回退现有 Markdown。IOC 发布后用 LangSmith 官方 `Client.push_prompt` 创建 Commit/Tag，真实运行同时写入 LangSmith metadata 和 IOC `ai_trace`。

**Tech Stack:** Python 3.11+、FastAPI、SQLAlchemy、Alembic、LangGraph、LangChain Core、LangSmith 0.9.x、pytest、Vue 3、TypeScript、Pinia、Element Plus、Vite。

## Global Constraints

- Prompt 配置必须融合到 `/infra/config`，不保留 Prompt、评估、实验、失败案例一级导航。
- 一期严格注册 `operation.analyze_reason`、`operation.generate_advice`、`report_chat.rag_decision`、`report_chat.query_rewrite`、`report_chat.generate_answer`。
- IOC 数据库是主数据源；现有 Markdown 永远保留为运行回退。
- 草稿和测试不得影响 production；只有管理员发布后 Graph 才切换版本。
- 运营人员不得更新 System Prompt、模型配置、输出 Schema、变量定义或执行发布/回滚。
- LangSmith 同步失败不得阻断 IOC 发布；必须保存失败状态并允许管理员重试。
- 测试命令默认设置 `LANGSMITH_TRACING=false`，不得上传测试数据。
- 保留用户现有未提交改动；每次只暂存当前任务明确列出的文件。

---

## File Structure

### Backend

- `app/modules/prompt_center/domain/builtin_prompts.py`：5 个内置 Prompt 的唯一注册表。
- `app/modules/prompt_center/application/bootstrap_service.py`：幂等初始化。
- `app/modules/prompt_center/application/authorization.py`：角色、权限和字段级校验。
- `app/modules/prompt_center/application/prompt_resolver.py`：production 解析与 Markdown 回退。
- `app/modules/prompt_center/application/langsmith_sync_service.py`：发布同步和重试。
- `app/modules/prompt_center/infrastructure/langsmith_client.py`：LangSmith SDK Adapter。
- `app/modules/prompt_center/application/prompt_release_service.py`：IOC 发布事务。
- `app/modules/prompt_center/api/*`：受权限保护的 Prompt API。
- `app/modules/prompt_center/infrastructure/models.py`：同步状态字段。
- `app/runtime/models/trace_model.py`：保持现有列，Prompt 扩展信息写入 `input_data.prompt_metadata`。
- `app/operation_agent/nodes/*.py`、`app/report_chat_agent/nodes/*.py`：5 个 Resolver 消费点。

### Frontend

- `src/pages/config-center/IndexPage.vue`：配置中心页签容器。
- `src/pages/config-center/prompt-center/*`：列表、编辑、测试、发布、指标组件。
- `src/api/prompt-center/index.ts`：统一走 `request()` 的 API Client。
- `src/stores/prompt-center.ts`：Prompt 页面状态。
- `src/router/index.ts`、`src/layouts/DefaultLayout.vue`：路由与导航收敛。
- `src/types/prompt-center.ts`：API 类型和权限类型。

### Tests

- `tests/prompt_center/test_builtin_bootstrap.py`
- `tests/prompt_center/test_authorization.py`
- `tests/prompt_center/test_lifecycle_api.py`
- `tests/prompt_center/test_langsmith_sync.py`
- `tests/prompt_center/test_prompt_resolver.py`
- 现有 Operation/Report Chat 节点测试文件。

---

### Task 1: Repair the migration chain and isolate the一期 schema

**Files:**

- Modify: `backend/alembic/versions/20260728_0001_create_prompt_center_tables.py`
- Modify: `backend/app/modules/prompt_center/infrastructure/models.py`
- Create: `backend/alembic/versions/20260728_0005_add_prompt_sync_status.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/prompt_center/test_migration_contract.py`

**Interfaces:**

- Produces: a single Alembic head containing Prompt Center tables and `langsmith_sync_*` fields.
- Produces: `PromptVersion.langsmith_sync_status`, `langsmith_sync_error`, `langsmith_synced_at`.

- [ ] **Step 1: Write the migration contract test**

```python
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_prompt_center_migrations_have_one_resolvable_head() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert script.get_revision("20260728_0001").down_revision is not None
```

- [ ] **Step 2: Run the test and confirm the missing revision failure**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_migration_contract.py -q
```

Expected: fail with the missing `20260711_0006_add_langgraph_runtime_prompt_facts` revision.

- [ ] **Step 3: Point `20260728_0001` to the current real head and add sync columns**

Set the incorrect Prompt Center parent revision:

```python
down_revision: str | None = "20260711_0006"
```

Create revision `20260728_0005` with:

```python
revision: str = "20260728_0005"
down_revision: str | None = "20260728_0004"
```

The new sync migration must add:

```python
op.add_column(
    "prompt_version",
    sa.Column("langsmith_sync_status", sa.String(32), nullable=False, server_default="pending"),
)
op.add_column("prompt_version", sa.Column("langsmith_sync_error", sa.Text(), nullable=True))
op.add_column("prompt_version", sa.Column("langsmith_synced_at", sa.DateTime(), nullable=True))
```

Do not register the evaluation, experiment, or failure models in `alembic/env.py` for this一期.

- [ ] **Step 4: Re-run migration checks**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_migration_contract.py -q
.venv/bin/alembic heads
```

Expected: test passes and Alembic prints exactly one head.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/env.py backend/alembic/versions/20260728_0001_create_prompt_center_tables.py backend/alembic/versions/20260728_0005_add_prompt_sync_status.py backend/app/modules/prompt_center/infrastructure/models.py backend/tests/prompt_center/test_migration_contract.py
git commit -m "fix: repair prompt center migrations"
```

### Task 2: Register and bootstrap the 5 real Prompts

**Files:**

- Create: `backend/app/modules/prompt_center/domain/builtin_prompts.py`
- Create: `backend/app/modules/prompt_center/application/bootstrap_service.py`
- Replace: `backend/scripts/seed_prompt_center.py`
- Test: `backend/tests/prompt_center/test_builtin_bootstrap.py`

**Interfaces:**

- Produces: `BUILTIN_PROMPTS: tuple[BuiltinPromptSpec, ...]`.
- Produces: `ensure_builtin_prompts(db: Session) -> BootstrapResult`.
- Consumes: existing Markdown files through absolute paths derived from module locations.

- [ ] **Step 1: Write failing registry and idempotency tests**

```python
def test_registry_contains_only_runtime_consumed_prompts() -> None:
    assert {item.prompt_key for item in BUILTIN_PROMPTS} == {
        "operation.analyze_reason",
        "operation.generate_advice",
        "report_chat.rag_decision",
        "report_chat.query_rewrite",
        "report_chat.generate_answer",
    }


def test_bootstrap_is_idempotent(db_session) -> None:
    first = ensure_builtin_prompts(db_session)
    second = ensure_builtin_prompts(db_session)

    assert first.created_prompts == 5
    assert second.created_prompts == 0
    assert prompt_def_repo.count(db_session) == 5
    assert prompt_version_repo.count(db_session) == 5
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_builtin_bootstrap.py -q
```

Expected: import failure for `builtin_prompts`.

- [ ] **Step 3: Implement the typed built-in registry**

```python
@dataclass(frozen=True)
class BuiltinPromptSpec:
    prompt_key: str
    prompt_name: str
    business_scene: str
    graph_name: str
    node_name: str
    system_path: Path | None
    template_paths: Mapping[str, Path]
    variables: tuple[BuiltinVariableSpec, ...]


BUILTIN_PROMPTS = (
    BuiltinPromptSpec(
        prompt_key="operation.generate_advice",
        prompt_name="运营分析—建议生成",
        business_scene="运营分析",
        graph_name="ioc_operation_analysis_graph",
        node_name="generate_advice",
        system_path=OPERATION_PROMPT_DIR / "system_prompt.md",
        template_paths={"default": OPERATION_PROMPT_DIR / "operation_advice.md"},
        variables=(
            BuiltinVariableSpec("abnormal_items", "异常项", "array", True),
            BuiltinVariableSpec("reason_analysis", "原因分析", "string", True),
            BuiltinVariableSpec("evidence", "证据", "array", False),
        ),
    ),
)
```

Define all five entries explicitly. For `report_chat.generate_answer`, store `report_answer` and `rag_answer` in `template_paths`.

Use these exact variants and required variables:

| Prompt Key | Variants | Required variables |
| --- | --- | --- |
| `operation.analyze_reason` | `default=operation_analysis.md` | `page_context`, `metrics`, `abnormal_items`, `evidence` |
| `operation.generate_advice` | `default=operation_advice.md` | `abnormal_items`, `reason_analysis`, `evidence` |
| `report_chat.rag_decision` | `default=rag_decision.md` | `user_question`, `question_scope`, `report_context`, `abnormal_items`, `risk_items`, `retrieved_context`, `evidence_refs` |
| `report_chat.query_rewrite` | `default=rag_query_rewrite.md` | `user_question`, `rag_intent`, `suggested_doc_types`, `required_anchors`, `report_context`, `abnormal_items`, `risk_items`, `advice_items`, `retrieved_context`, `scene` |
| `report_chat.generate_answer` | `report_answer=report_answer.md`, `rag_answer=rag_answer.md` | `user_question`, `report_context`, `retrieved_context`, `evidence`, `merged_context`, `rag_results`, `chat_history` |

- [ ] **Step 4: Implement create-only bootstrap**

`ensure_builtin_prompts()` must:

1. Query by Prompt Key.
2. Create definition, variables, `v1.0.0`, and production release only when absent.
3. Store `source_hash=sha256(system + variants)` inside `model_config["builtin_source_hash"]`.
4. Never update an existing Prompt, version, draft, or release pointer.

- [ ] **Step 5: Re-run tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_builtin_bootstrap.py -q
```

Expected: all bootstrap tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/prompt_center/domain/builtin_prompts.py backend/app/modules/prompt_center/application/bootstrap_service.py backend/scripts/seed_prompt_center.py backend/tests/prompt_center/test_builtin_bootstrap.py
git commit -m "feat: bootstrap built-in prompts"
```

### Task 3: Enforce two-role authorization and field protection

**Files:**

- Create: `backend/app/modules/prompt_center/application/authorization.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_routes.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_version_routes.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_release_routes.py`
- Modify: `backend/app/modules/prompt_center/schemas/version_schema.py`
- Modify: `frontend/src/utils/request.ts`
- Test: `backend/tests/prompt_center/test_authorization.py`

**Interfaces:**

- Produces: `require_prompt_permission(permission: PromptPermission)`.
- Produces: `assert_version_fields_allowed(payload: VersionUpdate, context: UserContext)`.
- Consumes: existing `get_user_context()`.

- [ ] **Step 1: Write failing permission tests**

```python
def test_operator_cannot_publish(client, operator_headers, approved_version) -> None:
    response = client.post(
        f"/api/v1/prompt-center/prompts/{approved_version.prompt_id}"
        f"/versions/{approved_version.id}/publish",
        headers=operator_headers,
        json={"environment": "production", "release_note": "forbidden"},
    )
    assert response.status_code == 403


def test_operator_cannot_update_system_content(client, operator_headers, draft_version) -> None:
    response = client.put(
        f"/api/v1/prompt-center/prompts/{draft_version.prompt_id}"
        f"/versions/{draft_version.id}",
        headers=operator_headers,
        json={"system_content": "forbidden"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_authorization.py -q
```

Expected: current API accepts the calls or lacks permission dependencies.

- [ ] **Step 3: Implement role and permission mapping**

```python
class PromptPermission(StrEnum):
    READ = "prompt:read"
    DRAFT_CREATE = "prompt:draft:create"
    DRAFT_UPDATE = "prompt:draft:update"
    PREVIEW = "prompt:preview"
    TEST = "prompt:test"
    SUBMIT = "prompt:submit"
    SYSTEM_UPDATE = "prompt:system:update"
    REVIEW = "prompt:review"
    PUBLISH = "prompt:publish"
    ROLLBACK = "prompt:rollback"
    LANGSMITH_RETRY = "prompt:langsmith:retry"
```

`prompt_operator` receives the first six permissions. `prompt_admin` receives every permission.

- [ ] **Step 4: Enforce field-level validation**

Reject these non-`None` fields for an operator:

```python
PROTECTED_VERSION_FIELDS = {
    "system_content",
    "llm_config",
    "output_schema",
}
```

Use the request `UserContext` for `created_by`, `operator_id`, `approved_by`, and `released_by`; remove those writable fields from API request schemas.

- [ ] **Step 5: Configure local-only identity headers**

In `request.ts`, only when `import.meta.env.DEV` is true, add:

```typescript
headers.set('X-User-Id', import.meta.env.VITE_LOCAL_USER_ID || 'local-admin')
headers.set('X-Roles', import.meta.env.VITE_LOCAL_USER_ROLES || 'prompt_admin')
```

Do not add `X-Permissions`; backend derives permissions from roles.

- [ ] **Step 6: Re-run authorization tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_authorization.py -q
```

Expected: all authorization tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/prompt_center/application/authorization.py backend/app/modules/prompt_center/api/prompt_routes.py backend/app/modules/prompt_center/api/prompt_version_routes.py backend/app/modules/prompt_center/api/prompt_release_routes.py backend/app/modules/prompt_center/schemas/version_schema.py backend/tests/prompt_center/test_authorization.py frontend/src/utils/request.ts
git commit -m "feat: enforce prompt center permissions"
```

### Task 4: Implement official LangSmith `push_prompt` synchronization

**Files:**

- Modify: `backend/app/modules/prompt_center/infrastructure/langsmith_client.py`
- Create: `backend/app/modules/prompt_center/application/langsmith_sync_service.py`
- Modify: `backend/app/modules/prompt_center/application/prompt_release_service.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_release_routes.py`
- Modify: `backend/app/modules/prompt_center/schemas/release_schema.py`
- Test: `backend/tests/prompt_center/test_langsmith_sync.py`

**Interfaces:**

- Produces: `LangSmithPushResult(commit_url: str, commit_hash: str | None)`.
- Produces: `LangSmithPromptClient.push_prompt(prompt_key, version_label, messages, variant=None)`.
- Produces: `sync_published_version(db, version_id) -> PromptVersion`.
- Consumes: `langsmith.Client.push_prompt`.

- [ ] **Step 1: Write failing SDK contract tests**

```python
def test_push_prompt_uses_official_sdk_contract(monkeypatch) -> None:
    fake = FakeLangSmithClient(push_url="https://smith.langchain.com/prompts/p/abc123")
    monkeypatch.setattr(langsmith_client, "_get_client", lambda: fake)

    result = langsmith_client.push_prompt(
        prompt_key="operation.generate_advice",
        version_label="1.2.0",
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "advice for {abnormal_items}"},
        ],
    )

    assert fake.calls[0]["prompt_identifier"] == "operation.generate_advice"
    assert fake.calls[0]["commit_tags"] == ["1.2.0", "production"]
    assert result.commit_url.endswith("/abc123")
```

Also test that a raised SDK exception returns a typed failure and never exposes the API key.

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_langsmith_sync.py -q
```

Expected: failure because the current code calls `create_prompt(name=...)` and `create_commit(prompt_id=..., messages=...)`.

- [ ] **Step 3: Implement `ChatPromptTemplate` conversion and `push_prompt`**

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages(
    [(message["role"], message["content"]) for message in messages]
)
commit_url = client.push_prompt(
    prompt_key,
    object=prompt,
    description=f"IOC Prompt {prompt_key}",
    commit_tags=[version_label, "production"],
    commit_description=f"IOC production release {version_label}",
)
```

Use the installed SDK return URL as `commit_url`, then retrieve the fixed production Commit:

```python
commit = client.pull_prompt_commit(
    f"{prompt_key}:production",
    include_model=False,
    skip_cache=True,
)
return LangSmithPushResult(
    commit_url=commit_url,
    commit_hash=commit.commit_hash,
)
```

Do not infer the hash by parsing the UI URL.

- [ ] **Step 4: Synchronize after the IOC release transaction**

Publication sequence:

1. Validate administrator permission and approved status.
2. Commit IOC release and production pointer.
3. Mark sync status `pending`.
4. Call `sync_published_version`.
5. Set `synced` plus commit information, or `failed` plus sanitized error.
6. Return HTTP 200 for both `synced` and `failed`; include sync status in response.

- [ ] **Step 5: Add the administrator retry endpoint**

```text
POST /api/v1/prompt-center/prompts/{prompt_id}/versions/{version_id}/langsmith/retry
```

Return the updated version sync fields.

- [ ] **Step 6: Run tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_langsmith_sync.py -q
```

Expected: all sync, failure, and retry tests pass without a remote call.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/prompt_center/infrastructure/langsmith_client.py backend/app/modules/prompt_center/application/langsmith_sync_service.py backend/app/modules/prompt_center/application/prompt_release_service.py backend/app/modules/prompt_center/api/prompt_release_routes.py backend/app/modules/prompt_center/schemas/release_schema.py backend/tests/prompt_center/test_langsmith_sync.py
git commit -m "feat: sync prompt releases to LangSmith"
```

### Task 5: Build the production Resolver and Prompt observability metadata

**Files:**

- Create: `backend/app/modules/prompt_center/application/prompt_resolver.py`
- Modify: `backend/app/modules/prompt_center/domain/entities.py`
- Modify: `backend/app/observability/langsmith_tracing.py`
- Test: `backend/tests/prompt_center/test_prompt_resolver.py`
- Modify: `backend/tests/observability/test_langsmith_tracing.py`

**Interfaces:**

- Produces: `ResolvedPrompt`.
- Produces: `resolve_prompt(prompt_key, variables, environment="production", variant=None)`.
- Produces: `prompt_trace_metadata(resolved, node_name) -> dict[str, object]`.

- [ ] **Step 1: Write Resolver behavior tests**

```python
def test_resolver_returns_published_version(db_session, published_prompt) -> None:
    result = resolve_prompt(
        db_session,
        "operation.generate_advice",
        variables={"abnormal_items": [], "reason_analysis": "", "evidence": []},
    )
    assert result.version_label == "1.2.0"
    assert result.fallback is False


def test_resolver_falls_back_when_repository_fails(monkeypatch, db_session) -> None:
    monkeypatch.setattr(prompt_release_repo, "get_active", raising_database_error)
    result = resolve_prompt(
        db_session,
        "operation.generate_advice",
        variables={"abnormal_items": [], "reason_analysis": "", "evidence": []},
    )
    assert result.version_label == "builtin"
    assert result.fallback is True
    assert result.fallback_reason == "database_error"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_prompt_resolver.py -q
```

Expected: import failure for `prompt_resolver`.

- [ ] **Step 3: Implement the stable Resolver result**

```python
@dataclass(frozen=True)
class ResolvedPrompt:
    prompt_id: int | None
    prompt_key: str
    version_id: int | None
    version_label: str
    messages: list[dict[str, str]]
    rendered_text: str
    langsmith_commit_hash: str | None
    fallback: bool
    fallback_reason: str | None
    variant: str | None
```

The Resolver must catch repository, missing release, missing variable, and render errors, then use the corresponding built-in registry entry.

- [ ] **Step 4: Add Prompt metadata to LangSmith config**

`build_langsmith_config()` already accepts `metadata`. Keep it generic and call it with:

```python
metadata={
    "prompt_key": resolved.prompt_key,
    "prompt_version": resolved.version_label,
    "prompt_version_id": resolved.version_id,
    "prompt_commit_hash": resolved.langsmith_commit_hash,
    "prompt_environment": "production",
    "prompt_variant": resolved.variant,
    "prompt_fallback": resolved.fallback,
    "node_name": node_name,
}
```

Extend tests to assert these values survive sanitization.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_prompt_resolver.py tests/observability/test_langsmith_tracing.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/prompt_center/application/prompt_resolver.py backend/app/modules/prompt_center/domain/entities.py backend/app/observability/langsmith_tracing.py backend/tests/prompt_center/test_prompt_resolver.py backend/tests/observability/test_langsmith_tracing.py
git commit -m "feat: resolve and trace prompt versions"
```

### Task 6: Connect the 5 real Graph nodes

**Files:**

- Modify: `backend/app/operation_agent/nodes/analyze_reason_node.py`
- Modify: `backend/app/operation_agent/nodes/generate_advice_node.py`
- Modify: `backend/app/report_chat_agent/nodes/should_use_rag_node.py`
- Modify: `backend/app/report_chat_agent/nodes/build_rag_query_node.py`
- Modify: `backend/app/report_chat_agent/nodes/generate_report_answer_node.py`
- Modify: `backend/app/operation_agent/state.py`
- Modify: `backend/app/report_chat_agent/state.py`
- Test: existing node test files plus `backend/tests/prompt_center/test_graph_prompt_integration.py`

**Interfaces:**

- Consumes: `resolve_prompt`.
- Produces: `state["prompt_usages"]`, a list of serialized Prompt metadata.
- Preserves: existing node outputs and deterministic LLM failure fallbacks.

- [ ] **Step 1: Add failing integration tests for each node**

```python
def test_generate_advice_uses_resolved_prompt(monkeypatch, operation_state) -> None:
    resolved = fake_resolved_prompt("operation.generate_advice", "1.2.0")
    monkeypatch.setattr(generate_advice_module, "resolve_prompt_for_node", lambda **_: resolved)

    result = generate_advice_node(operation_state)

    assert result["prompt_usages"][-1]["prompt_key"] == "operation.generate_advice"
    assert result["prompt_usages"][-1]["version_label"] == "1.2.0"
```

Add equivalent tests for all five nodes, including `report_answer` versus `rag_answer`.

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_graph_prompt_integration.py -q
```

Expected: missing `prompt_usages` or Resolver entry point.

- [ ] **Step 3: Replace direct Markdown loads with Resolver calls**

Each node:

1. Builds its variables dictionary.
2. Calls `resolve_prompt_for_node(prompt_key, variables, variant)`.
3. Extracts system/user messages.
4. Calls the existing LLM client.
5. Appends Prompt metadata to `state["prompt_usages"]`.
6. Preserves existing deterministic output fallback on LLM failure.

Do not remove Markdown files or built-in fallback loaders.

- [ ] **Step 4: Persist Prompt metadata in IOC Trace**

When the node writes or contributes to an LLM span, set:

```python
prompt_id=str(resolved.version_id) if resolved.version_id else None,
prompt_code=resolved.prompt_key,
prompt_version=resolved.version_id,
prompt_snapshot=resolved.rendered_text,
input_data={
    **existing_input_data,
    "prompt_metadata": resolved.to_trace_metadata(),
},
```

- [ ] **Step 5: Run focused Graph tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/prompt_center/test_graph_prompt_integration.py \
  tests/operation_agent/test_operation_graph.py \
  tests/report_chat_agent/test_should_use_rag_node.py \
  tests/report_chat_agent/test_build_rag_query_node.py \
  tests/report_chat_agent/test_generate_answer_with_rag.py -q
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/operation_agent/nodes/analyze_reason_node.py backend/app/operation_agent/nodes/generate_advice_node.py backend/app/report_chat_agent/nodes/should_use_rag_node.py backend/app/report_chat_agent/nodes/build_rag_query_node.py backend/app/report_chat_agent/nodes/generate_report_answer_node.py backend/app/operation_agent/state.py backend/app/report_chat_agent/state.py backend/tests/prompt_center/test_graph_prompt_integration.py backend/tests/operation_agent/test_operation_graph.py backend/tests/report_chat_agent/test_should_use_rag_node.py backend/tests/report_chat_agent/test_build_rag_query_node.py backend/tests/report_chat_agent/test_generate_answer_with_rag.py
git commit -m "feat: use published prompts in agent graphs"
```

### Task 7: Complete the Prompt lifecycle API and真实 metrics

**Files:**

- Modify: `backend/app/modules/prompt_center/application/prompt_service.py`
- Modify: `backend/app/modules/prompt_center/application/prompt_version_service.py`
- Modify: `backend/app/modules/prompt_center/application/prompt_test_service.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_routes.py`
- Modify: `backend/app/modules/prompt_center/api/prompt_test_routes.py`
- Modify: `backend/app/modules/prompt_center/schemas/*.py`
- Test: `backend/tests/prompt_center/test_lifecycle_api.py`

**Interfaces:**

- Produces: APIs listed in the design document.
- Produces: metrics derived from `ai_trace`, never mock constants.

- [ ] **Step 1: Write failing API workflow tests**

Create a single workflow test:

```python
def test_operator_draft_test_admin_publish_and_rollback(
    client, operator_headers, admin_headers, seeded_prompt
) -> None:
    draft = create_draft(client, operator_headers, seeded_prompt.id)
    run = test_draft(client, operator_headers, seeded_prompt.id, draft["id"])
    submit_draft(client, operator_headers, seeded_prompt.id, draft["id"])
    approve_draft(client, admin_headers, seeded_prompt.id, draft["id"])
    release = publish_draft(client, admin_headers, seeded_prompt.id, draft["id"])
    rollback = rollback_prompt(client, admin_headers, seeded_prompt.id)

    assert run["status"] in {"completed", "failed"}
    assert release["version_id"] == draft["id"]
    assert rollback["version_id"] != draft["id"]
```

Mock the LLM and LangSmith clients; use real FastAPI routes and SQLAlchemy repositories.

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_lifecycle_api.py -q
```

Expected: workflow fails on current contracts or status transitions.

- [ ] **Step 3: Align lifecycle schemas and services**

Rules:

- `POST /versions` copies the current production version into a new draft.
- `PUT /versions/{id}` only edits draft/rejected versions.
- Preview and test accept explicit `version_id`.
- Operator identity comes from `UserContext`.
- Publication is production-only in一期; remove the gray-release UI path.
- Rollback selects the previous active production release deterministically by `released_at DESC`.

- [ ] **Step 4: Implement真实 metrics**

Aggregate `ai_trace` by `prompt_code` and `prompt_version`:

- `total_runs`
- `total_failures`
- `avg_tokens`
- `avg_latency_ms`
- per-version counts

Return `null` for rates that have no evaluation records. Never synthesize display values.

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center/test_lifecycle_api.py -q
```

Expected: complete workflow and metrics tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/prompt_center/application backend/app/modules/prompt_center/api backend/app/modules/prompt_center/schemas backend/tests/prompt_center/test_lifecycle_api.py
git commit -m "feat: complete prompt lifecycle api"
```

### Task 8: Merge Prompt UI into the existing configuration center

**Files:**

- Modify: `frontend/src/pages/config-center/IndexPage.vue`
- Create: `frontend/src/pages/config-center/prompt-center/PromptListPanel.vue`
- Create: `frontend/src/pages/config-center/prompt-center/PromptEditorPage.vue`
- Create: `frontend/src/pages/config-center/prompt-center/PromptTestPage.vue`
- Create: `frontend/src/pages/config-center/prompt-center/PromptReleasePage.vue`
- Create: `frontend/src/pages/config-center/prompt-center/PromptMetricsPage.vue`
- Modify: `frontend/src/api/prompt-center/index.ts`
- Modify: `frontend/src/stores/prompt-center.ts`
- Modify: `frontend/src/types/prompt-center.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/DefaultLayout.vue`
- Modify: `frontend/src/main.ts`
- Delete after porting: `frontend/src/views/evaluation-center/*`, `frontend/src/views/experiment-center/*`, `frontend/src/views/failure-center/*`

**Interfaces:**

- Consumes: backend lifecycle and metrics APIs.
- Produces: `/infra/config/prompts*` routes.

- [ ] **Step 1: Correct the API client before UI work**

Replace double requests such as:

```typescript
request(`${BASE}`).then(() => fetch(BASE))
```

with:

```typescript
export function listPrompts(params: PromptListQuery) {
  return request<PaginatedResult<PromptDefinition>>(
    buildPath('/prompt-center/prompts', params),
  )
}
```

Every API call must use `request()` so `/api/v1` and Trace headers are preserved.

- [ ] **Step 2: Run the build to capture existing failures**

Run:

```bash
cd frontend
npm run build
```

Expected: current Element Plus locale and Prompt page TypeScript errors fail the build.

- [ ] **Step 3: Implement the configuration tabs and nested routes**

`IndexPage.vue` owns tabs:

```typescript
const tabs = [
  { key: 'runtime', label: '运行环境', to: '/infra/config' },
  { key: 'prompts', label: 'Prompt 配置', to: '/infra/config/prompts' },
]
```

Routes:

```text
/infra/config/prompts
/infra/config/prompts/:id/edit
/infra/config/prompts/:id/test
/infra/config/prompts/:id/release
/infra/config/prompts/:id/metrics
```

- [ ] **Step 4: Implement role-sensitive UI**

Load `/context/current`. For `prompt_operator`:

- show edit business fields, preview, test, submit.
- hide System/model/schema fields and publish/rollback.

For `prompt_admin`, show every control. Backend remains authoritative.

- [ ] **Step 5: Remove一期-out-of-scope navigation and fix build errors**

Remove independent Prompt/evaluation/experiment/failure links. Import Element Plus locale through a typed public entry point or add a narrow module declaration. Remove unused variables and correct summary/full-version type mismatches.

- [ ] **Step 6: Verify frontend**

Run:

```bash
cd frontend
npm run type-check
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/config-center frontend/src/api/prompt-center frontend/src/stores/prompt-center.ts frontend/src/types/prompt-center.ts frontend/src/router/index.ts frontend/src/layouts/DefaultLayout.vue frontend/src/main.ts frontend/package.json frontend/pnpm-lock.yaml
git add -u frontend/src/views/evaluation-center frontend/src/views/experiment-center frontend/src/views/failure-center
git commit -m "feat: add prompts to configuration center"
```

### Task 9: End-to-end verification and safe LangSmith smoke trace

**Files:**

- Create: `backend/scripts/verify_prompt_center.py`
- Modify: `backend/README.md`
- Modify: `docs/superpowers/specs/2026-07-28-prompt-center-minimal-loop-design.md` only if implementation revealed a confirmed contract correction.

**Interfaces:**

- Produces: deterministic local acceptance output.
- Produces: optional synthetic remote LangSmith verification with no IOC business data.

- [ ] **Step 1: Implement the local verifier**

The verifier must check:

1. exactly 5 built-in Prompt definitions.
2. one active production release per Prompt.
3. Resolver metadata for all five.
4. operator/admin permission matrix.
5. LangSmith configuration health without printing the key.

- [ ] **Step 2: Run focused and full backend tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/prompt_center -q
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
.venv/bin/alembic heads
.venv/bin/python scripts/verify_prompt_center.py
```

Expected: zero failures, one Alembic head, verifier exits 0.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd frontend
npm run type-check
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 4: Verify local UI**

Start backend and frontend, then verify:

- `/infra/config/prompts` lists five items.
- operator cannot see or call publish.
- admin can open release and metrics pages.
- a test run displays the rendered Prompt and real Token/latency fields.

- [ ] **Step 5: Run an optional synthetic LangSmith smoke check**

Only after confirming the payload contains no IOC data:

- publish a synthetic Prompt named `ioc-prompt-smoke`.
- emit a synthetic trace containing `prompt_key=ioc-prompt-smoke`.
- query LangSmith by that metadata and confirm the remote Run exists.
- delete the synthetic Prompt with `client.delete_prompt("ioc-prompt-smoke")` after the query succeeds.

Do not send a real Operation or Report Chat request without separate user authorization.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/verify_prompt_center.py backend/README.md
git commit -m "test: verify prompt center minimal loop"
```
