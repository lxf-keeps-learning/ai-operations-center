# LangSmith Prompt 自动同步实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Prompt 灰度/正式发布前将不可变版本自动同步到 LangSmith Prompt Hub，并以严格失败语义保护当前有效发布。

**Architecture:** IOC 继续作为发布控制面；基础设施客户端负责构造和推送 `ChatPromptTemplate`，应用层同步服务负责复用或持久化 Commit，发布服务在任何本地发布变更前调用同步服务。同步默认关闭，测试全部使用 Fake Client。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、LangSmith 0.9.x、LangChain Core 1.4.x、pytest。

## Global Constraints

- `LANGSMITH_PROMPT_SYNC_ENABLED=false` 为默认值，并与 Trace 开关独立。
- 同步开启时，API Key 缺失或远程失败返回 `PROMPT_SYNC_FAILED`（HTTP 502）并阻止发布。
- 同一 Prompt Version 已有 Commit 时必须复用；回滚不得创建 Commit。
- Prompt 必须保持 private；不得记录 API Key、完整 Prompt 或远程响应正文。
- 不进行真实远程上传。

---

### Task 1: 配置、错误契约与 Prompt Hub 客户端

**Files:**
- Modify: `backend/app/config/settings.py`
- Modify: `backend/app/core/exception/error_code.py`
- Modify: `backend/app/modules/prompt_center/domain/exceptions.py`
- Modify: `backend/app/modules/prompt_center/infrastructure/langsmith_client.py`
- Create: `backend/tests/modules/prompt_center/test_langsmith_prompt_client.py`

**Interfaces:**
- Produces: `PromptSyncResult(commit_hash: str, tag: str, url: str)`
- Produces: `LangSmithPromptClient.push_prompt(prompt, version) -> PromptSyncResult`
- Produces: `PROMPT_SYNC_FAILED` with HTTP 502.

- [ ] **Step 1: Write failing client tests**

Cover the exact `Client.push_prompt(prompt_identifier=..., object=..., is_public=False, tags=..., commit_tags=..., commit_description=...)` call, literal-brace escaping, URL hash parsing, malformed URL, SDK exception, and missing API key.

- [ ] **Step 2: Run client tests and verify RED**

Run: `cd backend && LANGSMITH_PROMPT_SYNC_ENABLED=false .venv/bin/pytest -q tests/modules/prompt_center/test_langsmith_prompt_client.py`

Expected: collection/import or assertion failures because the new contract does not exist.

- [ ] **Step 3: Implement the minimal client contract**

Add the independent setting and error code. Build a two-message `ChatPromptTemplate`; escape literal braces in stored content while preserving only `{runtime_context}` and `{user_question}`. Call the installed LangSmith SDK using its 0.9.x keyword contract and parse the short Commit Hash from either `/prompts/<name>/<hash>` or `/hub/<owner>/<name>:<hash>`.

- [ ] **Step 4: Run client tests and verify GREEN**

Run the Task 1 pytest command and require zero failures.

### Task 2: 同步服务与严格发布集成

**Files:**
- Create: `backend/app/modules/prompt_center/application/prompt_sync_service.py`
- Modify: `backend/app/modules/prompt_center/application/prompt_release_service.py`
- Create: `backend/tests/modules/prompt_center/test_prompt_sync_release.py`

**Interfaces:**
- Consumes: `LangSmithPromptClient.push_prompt(prompt, version)`.
- Produces: `ensure_prompt_version_synced(db, prompt, version) -> PromptSyncResult | None`.

- [ ] **Step 1: Write failing service and release tests**

Cover disabled sync, first sync persistence, existing Commit reuse, missing key/remote failure, gray and production release, active-release preservation on failure, audit metadata, and rollback without sync.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `cd backend && LANGSMITH_PROMPT_SYNC_ENABLED=false .venv/bin/pytest -q tests/modules/prompt_center/test_prompt_sync_release.py`

Expected: failures because the synchronization service and release hook do not exist.

- [ ] **Step 3: Implement minimal synchronization and release hook**

Call `ensure_prompt_version_synced` after status validation and before `deactivate_env`. Persist `langsmith_commit_hash` and `langsmith_tag`, reuse existing values, convert infrastructure failures to the safe 502 business error, and add Commit data to publish audit `after_data`. Do not modify rollback flow.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run the Task 2 pytest command and require zero failures.

### Task 3: Configuration and project documentation

**Files:**
- Modify: `backend/.env.example`
- Modify: `backend/README.md`
- Modify: `docs/v2-prompt/项目总结.md`
- Modify: `docs/v2-prompt/项目面试.md`

- [ ] **Step 1: Document offline and strict modes**

Document the independent switch, required secret, strict publish behavior, Commit reuse, Trace association, and the fact that this run uses Fake Client rather than real upload.

- [ ] **Step 2: Verify documentation and whitespace**

Run: `git diff --check`

Expected: exit 0.

### Task 4: Full verification and integration

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run Prompt synchronization and V2 suites**

Run: `cd backend && LANGSMITH_PROMPT_SYNC_ENABLED=false .venv/bin/pytest -q tests/modules/prompt_center tests/modules/test_v2_prompt_acceptance.py`

- [ ] **Step 2: Run the full backend suite**

Run: `cd backend && LANGSMITH_PROMPT_SYNC_ENABLED=false .venv/bin/pytest -q`

- [ ] **Step 3: Verify Alembic and frontend**

Run: `cd backend && .venv/bin/alembic heads`

Run: `cd frontend && npm run type-check && npm run build`

- [ ] **Step 4: Inspect staged scope and secrets**

Run `git diff --check`, inspect `git status`, and confirm no `.env`, API key, `.superpowers/`, or `frontend/pnpm-lock.yaml` is staged.

- [ ] **Step 5: Commit, push, merge to `master`, re-run merged verification, and push `master`**

Use non-force pushes. Stop on rejected push, merge conflict, or failing merged verification.
